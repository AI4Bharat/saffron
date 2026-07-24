# Benchmark Verification Tasks

Human verification of TTS benchmark sentences. For every item an annotator checks
the **`raw_text`** and the **`spoken_form`**, edits either if needed, and marks the
item **Accept** or **Reject** (with an optional comment for rejections). The export
reproduces the original JSONL exactly, with only the annotation fields updated.

- **`test_type`:** `benchmark-verification`
- **Task name / batch:** `benchmark_<lang>_batch<n>` (200 items per batch)
- **Languages (10):** bn, gu, hi, kn, ml, mr, or, ta, te, ur

---

## 1. Input data

`backend/benchmark_tasks/<lang>.jsonl` — one object per line. Example line:

```json
{"id":"hi_casual_dialogue_00001","lang":"hi","suite":"domain","domain":"casual_dialogue",
 "phenomenon_tags":[],"raw_text":"चाय पियोगे या कॉफी?","spoken_form":"चाय पियोगे या कॉफी?",
 "length_bucket":"short","quota_class":"plain","target_emotion":null,
 "probes_axes":["expressiveness"],"source":"gemini","qa_status":"pending",
 "batch_id":"bench_20260724_044241","model":"gemini-3.1-pro-preview","gen_index":0}
```

`benchmark_tasks/manifests/*.summary.json` are the generator's per-batch summaries
(not used by the app).

---

## 2. Loading tasks into the DB

`backend/load_benchmark_tasks.py` splits each `<lang>.jsonl` into batches of 200 and
creates one `Test` row per batch:

```bash
cd /root/saffron/backend
venv/bin/python load_benchmark_tasks.py            # load every <lang>.jsonl
venv/bin/python load_benchmark_tasks.py hi         # one language
venv/bin/python load_benchmark_tasks.py hi bn ta   # a subset
BATCH_SIZE=250 venv/bin/python load_benchmark_tasks.py hi
```

- Stored `Test.json_entry` is the **byte-for-byte original** object list (so export
  can reproduce the exact input format).
- `description = "benchmark_<lang>_batch<n> — <LanguageName>"` (the language name lets
  the admin dashboard group by language).
- **Idempotent:** re-running matches an existing batch by its `benchmark_<lang>_batch<n>`
  name token and **updates in place** — never duplicates.

Current DB Test IDs (initial load, 2026-07-24):

| Lang | Batches | Test IDs |
|------|---------|----------|
| hi | 5 | 20944–20948 |
| bn | 5 | 20949–20953 |
| gu | 5 | 20954–20958 |
| kn | 5 | 20959–20963 |
| ml | 5 | 20964–20968 |
| mr | 5 | 20969–20973 |
| or | 5 | 20974–20978 |
| ta | 5 | 20979–20983 |
| te | 5 | 20984–20988 |
| ur | 5 | 20989–20993 |

> Batches are **unassigned** by default, so any annotator can open them. Assign them
> to specific annotators from the admin dashboard if you want them locked.

---

## 3. Annotation UI

`frontend/src/components/BenchmarkVerification.vue`, dispatched by `test_type`
in `TestView.vue` and `DynamicTestView.vue`.

- **Raw Text** and **Spoken Form** are click-to-edit textareas (each has a Reset).
- **Accept / Reject** buttons record the decision.
- **Comment** field labelled *(for rejection)* — optional.
- Shortcuts: `1` = accept, `2` = reject, `Ctrl/⌘+Enter` = submit & next,
  `Ctrl/⌘+S` = save draft. Save / Skip / Submit work like the other task types.
- Right-to-left rendering is automatic for Urdu.

Saved drafts and completed items re-open exactly as left: the backend `get_test`
merges `raw_text`, `spoken_form`, `decision`, and `comments` back into each item.

---

## 4. Admin review of submitted annotations

In the admin dashboard **Tasks Overview**, clicking any task opens
`/admin/task/<test_id>` (`AdminTaskReview.vue`). This renders the **same annotation
UI** the annotator used, but **read-only** and **pre-filled** with what was submitted:

- **One tab per annotator** — switch tabs to see each person's submission.
- A **Blank task** tab previews the empty task. When *no* annotations exist yet, the
  blank task is shown by default.
- An **Open fresh empty page** button opens the real, editable blank task in a new tab.
- The task components are read-only via a `readonly` prop (default `false`, so the
  **annotator experience is unchanged**): action buttons are hidden and every
  submit/save/skip path is inert, so the admin can never overwrite annotations.

Backend: `GET /api/admin/task/<test_id>/annotations` (admin only) returns the task's
items plus, per annotator, their latest submission for each item. Read-only.

---

## 5. Export back to JSONL

`backend/export_benchmark_jsonl.py`. Every line is the **exact original object**;
for items an annotator **completed**, these fields are merged in:

| Field | Value |
|-------|-------|
| `qa_status` | `true` (item verified) |
| `raw_text` | annotator's edited value |
| `spoken_form` | annotator's edited value |
| `decision` | `"accept"` or `"reject"` |
| `comment` | annotator's comment (only when non-empty) |

Items nobody completed are emitted **unchanged** (`qa_status` stays `"pending"`).
If several annotators rated an item, the **latest completed** submission wins.

```bash
cd /root/saffron/backend
# one batch by DB id
venv/bin/python export_benchmark_jsonl.py --test-id 20944 out.jsonl
# a whole language (all its batches merged, in order)
venv/bin/python export_benchmark_jsonl.py --lang hi hi.jsonl
# every language -> exported/<lang>.jsonl
venv/bin/python export_benchmark_jsonl.py --all exported/
```

A no-annotation export is a **lossless round-trip** of the input file (verified).

### One-command sync from Windows

`C:\Users\Avnish\benchmark_export_sync.ps1` runs the export on the server and downloads the
JSONL files to your machine:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\benchmark_export_sync.ps1
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\benchmark_export_sync.ps1 -Lang hi
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\benchmark_export_sync.ps1 -TestId 20944
```

Downloads land in `C:\Users\Avnish\benchmark_exports\<timestamp>\` by default
(override with `-OutDir`).

---

## 6. Deploying changes

```bash
# frontend
cd /root/saffron/frontend && npm run build      # served by Caddy from dist/
# backend restart (single gunicorn instance in tmux 'saffron')
tmux kill-session -t saffron 2>/dev/null; tmux new-session -d -s saffron \
  'bash /root/saffron/backend/start_saffron.sh 2>&1 | tee -a /root/saffron/backend/gunicorn.log'
```

Backend serves on `127.0.0.1:4020` (Caddy proxies `/api*`); 1 master + 6 workers.
