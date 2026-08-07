# Benchmark Evaluation V2 Tasks (round 3)

Human verification of the **v2** TTS benchmark set. Same annotator experience as the
earlier rounds: for each item the annotator checks the **`raw_text`** and the
**`spoken_form`**, edits either if needed, and marks the item **Accept** or **Reject**
(a comment is required on a rejection). The JSONL export reproduces the original input
exactly, with only the annotation fields updated.

| | |
|---|---|
| **`test_type`** | `benchmark-evaluation-v2` |
| **Task name / batch** | `benchmark_evaluation_v2_<lang>_batch<n>` (200 items per batch) |
| **Languages (10)** | bn, gu, hi, kn, ml, mr, or, ta, te, ur — English is reference-only, not annotated |
| **Input** | `backend/benchmark_tasks_v2/<lang>.jsonl` |
| **Loaded** | 2026-07-30 — 79 batches, Test IDs **21042–21128**, 14,309 items |

This is the **third** round and it stands completely apart from the earlier two:

| Round | `test_type` | Task names | Test IDs | Input |
|---|---|---|---|---|
| 1 | `benchmark-verification` | `benchmark_<lang>_batch<n>` | 20944–20993 | `benchmark_tasks/` |
| 2 | `benchmark-parallel` | `benchmark_parallel_<lang>_batch<n>` | 20994–21037 | `benchmark_tasks_new/` |
| **3** | **`benchmark-evaluation-v2`** | **`benchmark_evaluation_v2_<lang>_batch<n>`** | **21042–21128** (no en) | **`benchmark_tasks_v2/`** |

> **Why a separate round and not an update of round 2.** The v2 files reuse the round-2
> item ids (`hi_casual_dialogue_00001`, …) but **every sentence behind them is new** — a
> byte-for-byte comparison of the shared ids found *zero* matching `raw_text` values.
> Round 2 already carries 2,090 annotations (gu, hi, ml). Loading v2 over those Test rows
> would have silently re-pointed finished annotations at different sentences. The three
> rounds are queried, annotated and exported independently.

---

## 1. Input data

One JSON object per line, 17 fields, identical shape across all 15,805 rows:

```json
{"id":"hi_casual_dialogue_00001","lang":"hi","suite":"domain","domain":"casual_dialogue",
 "source_id":"en_casual_dialogue_00001","phenomenon_tags":[],
 "raw_text":"आज रात Paradise से ही कुछ बिरयानी ऑर्डर कर लेते हैं, …",
 "spoken_form":"आज रात पैराडाइज़ से ही कुछ बिरयानी ऑर्डर कर लेते हैं, …",
 "length_bucket":"short","quota_class":"plain","target_emotion":null,
 "probes_axes":["expressiveness"],"source":"gemini","qa_status":"pending",
 "batch_id":"parallel_tx_20260730_030615","model":"gemini-3.1-pro-preview","gen_index":0}
```

### What is in the set

| Lang | Items | Batches | Test IDs | English ref resolved |
|------|-------|---------|----------|----------------------|
| bn | 1486 | 8 | 21042–21049 | 760 |
| ~~en~~ | ~~1496~~ | — | *deleted 2026-07-30* | — (reference only) |
| gu | 1465 | 8 | 21058–21065 | 757 |
| hi | 1494 | 8 | 21066–21073 | 762 |
| kn | 1444 | 8 | 21074–21081 | 735 |
| ml | 1436 | 8 | 21082–21089 | 741 |
| mr | 1496 | 8 | 21090–21097 | 762 |
| or | 1217 | 7 | 21098–21104 | 584 |
| ta | 1415 | 8 | 21105–21112 | 700 |
| te | 1404 | 8 | 21113–21120 | 690 |
| ur | 1452 | 8 | 21121–21128 | 730 |
| **Total** | **14,309** | **79** | **21042–21128** | **7,221** |

- **New in v2: a `stress` suite** alongside `domain` (~6,240 stress / ~9,565 domain).
  Stress rows are generated directly in-language, so most have `source_id: null` and
  simply render no English reference — the UI already handles that.
- `batch_id` shows the generator run: `parallel_tx_*`, `stress_*`, `bench_*`,
  `topup_*`, `numbers_seed1234`.
- **English is not an annotation target.** `en.jsonl` stays in `benchmark_tasks_v2/`
  because it is what every other language's `source_id` resolves against, but the
  8 English batches (21050–21057) were **deleted on 2026-07-30**, and
  `SKIP_LANGS = {"en"}` in the loader stops a bare re-run from recreating them.
  To load them anyway, name the language explicitly:
  `load_benchmark_evaluation_v2_tasks.py en`.
- **Validated at load:** no duplicate item ids within a language, no empty `raw_text`
  or `spoken_form`, and **every** `source_id` resolves against `en.jsonl` (0 dangling).
- `benchmark_tasks_v2/manifests/*.summary.json` are the generator's per-batch
  summaries — not used by the app.

---

## 2. Loading tasks into the DB

`backend/load_benchmark_evaluation_v2_tasks.py` splits each `<lang>.jsonl` into batches
of 200 and creates one `Test` row per batch.

```bash
cd /root/saffron/backend
venv/bin/python load_benchmark_evaluation_v2_tasks.py --dry-run   # validate, write nothing
venv/bin/python load_benchmark_evaluation_v2_tasks.py             # load every <lang>.jsonl
venv/bin/python load_benchmark_evaluation_v2_tasks.py hi          # one language
venv/bin/python load_benchmark_evaluation_v2_tasks.py hi bn ta    # a subset
BATCH_SIZE=250 venv/bin/python load_benchmark_evaluation_v2_tasks.py hi
```

- `description = "benchmark_evaluation_v2_<lang>_batch<n> — <LanguageName>"`. The name
  token is the batch key; the language name is what the admin dashboard groups by.
- **The English source is attached to every translated item** so the annotation UI can
  show what the sentence is supposed to say. The loader indexes `en.jsonl` by `id`,
  resolves each item's `source_id`, and appends three keys — everything else is stored
  byte-for-byte unchanged:

  | Key | Value |
  |---|---|
  | `_ref_source_lang` | `"en"` |
  | `_ref_source_raw_text` | the English source `raw_text` |
  | `_ref_source_spoken_form` | the English source `spoken_form` |

  The `_ref_` prefix is the contract: **every exporter strips `_ref_*`**, so the
  round-trip stays lossless.
- **Idempotent:** a re-run matches an existing batch by its
  `benchmark_evaluation_v2_<lang>_batch<n>` token and updates it in place. Never
  duplicates. (Verified: a second `--dry-run` reports 87 updates, 0 creates.)
- Test ids come from SQLite autoincrement (no `max(id)+1` race).

Batches are **unassigned** by default, so any annotator can open them. Assign them
from the admin dashboard to lock them to specific people.

---

## 3. Annotation UI

`frontend/src/components/BenchmarkVerification.vue`, dispatched by `test_type` in
`TestView.vue`, `DynamicTestView.vue` and `AdminTaskReview.vue` — the same component
serves all three benchmark rounds, so the annotator experience is unchanged from
round 2. Reference panel (phenomenon tags, English source, domain/suite/length/quota/
emotion/axes), click-to-edit Raw Text and Spoken Form with Edited/Original + Reset +
Compare, Accept/Reject with quick-reason chips, comment required on reject, automatic
RTL for Urdu.

Shortcuts: `1` accept · `2` reject · `R` toggle reference · `Ctrl/⌘+Enter` submit &
next · `Ctrl/⌘+S` save draft.

Order, drafts, and multi-annotator vs handoff behave exactly as in the earlier rounds —
see [BENCHMARK_PARALLEL_TASKS.md](BENCHMARK_PARALLEL_TASKS.md) §4.

---

## 4. Admin review

`/admin/task/<test_id>` renders the same annotation UI, read-only and pre-filled, with
one tab per annotator plus a blank-task tab, backed by
`GET /api/admin/task/<test_id>/annotations`. An admin can never overwrite an annotation
from this page.

---

## 5. Exports

### 5a. JSONL — `export_benchmark_evaluation_v2_jsonl.py`

Every line is the **exact original object** (all 17 fields, original key order);
`_ref_*` and `completion_status` are stripped. For items an annotator **completed**:

| Field | Value |
|-------|-------|
| `qa_status` | `true` |
| `raw_text` | annotator's edited value |
| `spoken_form` | annotator's edited value |
| `decision` | `"accept"` or `"reject"` |
| `comment` | annotator's comment (only when non-empty) |

Items nobody completed are emitted unchanged (`qa_status` stays `"pending"`). If several
annotators rated an item, the **latest completed** submission wins.

```bash
# one batch by DB id
venv/bin/python export_benchmark_evaluation_v2_jsonl.py --test-id 21066 out.jsonl

# a whole language (all its batches, in batch order)
venv/bin/python export_benchmark_evaluation_v2_jsonl.py --lang hi hi.jsonl

# every language -> OUTDIR/<lang>.jsonl
venv/bin/python export_benchmark_evaluation_v2_jsonl.py --all exported_v2/

# ... plus a domain / phenomenon-tag accept-reject breakdown
venv/bin/python export_benchmark_evaluation_v2_jsonl.py --all exported_v2/ \
    --summary exported_v2/summary.json
```

**Verified lossless:** exporting with zero annotations reproduces the input files
object-for-object *and* key-order-for-key-order — checked across all 11 languages at
load time (15,805/15,805 rows); 14,309 rows over 10 languages now that English is out.

### 5b. Excel — `export_benchmark_excel.py --round v2`

Review-ready workbook: `Annotations` (original vs corrected side by side),
`All Submissions` (every submission incl. drafts and skips), `Rejections`, `Edits`,
`By Domain`, `By Phenomenon`, `By Language`, `By Annotator`, `Overview`.

```bash
venv/bin/python export_benchmark_excel.py --round v2 --all exported_v2_xlsx/
venv/bin/python export_benchmark_excel.py --round v2 --lang hi hi.xlsx
venv/bin/python export_benchmark_excel.py --round v2 --test-id 21066 batch.xlsx

# all three rounds in one workbook
venv/bin/python export_benchmark_excel.py --round all --lang hi hi_all_rounds.xlsx
```

`--round` accepts `v2` (this round), `parallel` (round 2, still the **default**), `v1`
(round 1) or `all`. The default was deliberately left at `parallel` so the round-2
commands already in use keep working — always pass `--round v2` for this round.

### 5c. Admin CSV — `/api/admin/export_csv/<test_id>`

The dashboard's per-task CSV now emits the full benchmark column set for
`benchmark-evaluation-v2` (Language, Suite, Domain, Phenomenon Tags, Probes Axes,
Quota Class, Length Bucket, Target Emotion, Source ID, English Raw/Spoken, Original vs
Corrected Raw/Spoken with a Changed flag, Decision, Comments).

---

## 6. Files touched

| File | Change |
|---|---|
| `backend/load_benchmark_evaluation_v2_tasks.py` | **new** — loader (`SKIP_LANGS = {"en"}`) |
| `backend/export_benchmark_evaluation_v2_jsonl.py` | **new** — JSONL export |
| `backend/export_benchmark_excel.py` | added the `v2` round (`--round v2`) |
| `backend/application/views.py` | `benchmark-evaluation-v2` added to the two CSV-export blocks |
| `frontend/src/views/TestView.vue` | dispatch `benchmark-evaluation-v2` → `BenchmarkVerification` |
| `frontend/src/views/DynamicTestView.vue` | same |
| `frontend/src/views/AdminTaskReview.vue` | same |

Rounds 1 and 2 (scripts, Test rows, and all 2,090 existing annotations) are untouched.
Pre-load DB snapshot: `backend/instance/database.db.bak_prev2_20260730_123516`.
