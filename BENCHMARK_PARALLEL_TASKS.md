# Parallel Benchmark Verification Tasks (round 2)

Human verification of the **parallel** TTS benchmark set: every non-English sentence
is a translation of an English source sentence, so the annotator can check the
translation against what it was supposed to say.

For each item an annotator checks the **`raw_text`** and the **`spoken_form`**,
edits either if needed, and marks the item **Accept** or **Reject** (a comment is
required on a rejection). The JSONL export reproduces the original input exactly,
with only the annotation fields updated.

| | |
|---|---|
| **`test_type`** | `benchmark-parallel` |
| **Task name / batch** | `benchmark_parallel_<lang>_batch<n>` (200 items per batch) |
| **Languages (11)** | bn, en, gu, hi, kn, ml, mr, or, ta, te, ur |
| **Input** | `backend/benchmark_tasks_new/<lang>.jsonl` |
| **Loaded** | 2026-07-25 — 44 batches, Test IDs **20994–21037**, 8133 items |

This is the second round. The first round (`benchmark-verification`,
`benchmark_<lang>_batch<n>`, Test IDs 20944–20993) is documented in
[BENCHMARK_TASKS.md](BENCHMARK_TASKS.md) and is untouched by any of this — the two
rounds live side by side, are queried separately, and export separately.

---

## 1. Input data

One JSON object per line. Example (`hi.jsonl`):

```json
{"id":"hi_casual_dialogue_00001","lang":"hi","suite":"domain","domain":"casual_dialogue",
 "source_id":"en_casual_dialogue_00001","phenomenon_tags":[],
 "raw_text":"आज का क्या प्रोग्राम है?","spoken_form":"आज का क्या प्रोग्राम है?",
 "length_bucket":"short","quota_class":"plain","target_emotion":null,
 "probes_axes":["expressiveness"],"source":"gemini","qa_status":"pending",
 "batch_id":"parallel_tx_20260724_173219","model":"gemini-3.1-pro-preview","gen_index":0}
```

### What is in the set

| Field | Values |
|---|---|
| `suite` | `domain` (all 8133 items) |
| `domain` | 22 domains — casual_dialogue, voice_assistant, customer_support, chatbot_longform, news, sports_commentary, weather, podcast_interview, audiobook_narration, advertisement, education, stem_scientific, encyclopedic, finance_banking, ecommerce_retail, travel_navigation, healthcare_medical, legal_government, technology_it, emotional_expressive, agriculture_rural, recipes_food |
| `phenomenon_tags` | 50 distinct tags — numbers, exclamations, code_mix, place_names, dates, units, brand_names, questions, technical_terms, lists, emotion, prices, acronyms, account_numbers, times, … |
| `quota_class` | `domain_natural` (4971), `plain` (1690), `hardest_edge` (1472) |
| `probes_axes` | `intelligibility` (5888), `expressiveness` (2990) |
| `target_emotion` | null on 6653; otherwise excitement, enthusiasm, suspense, warmth, joy, anger, sarcasm, fear, neutral, sadness |
| `source_id` | Points at the `en.jsonl` row this sentence was translated from. **All 7363 non-English items resolve.** English rows have `source_id: null`. |

`benchmark_tasks_new/manifests/*.summary.json` are the generator's per-batch
summaries — not used by the app.

---

## 2. Loading tasks into the DB

`backend/load_benchmark_parallel_tasks.py` splits each `<lang>.jsonl` into batches
of 200 and creates one `Test` row per batch.

```bash
cd /root/saffron/backend
venv/bin/python load_benchmark_parallel_tasks.py --dry-run   # validate, write nothing
venv/bin/python load_benchmark_parallel_tasks.py             # load every <lang>.jsonl
venv/bin/python load_benchmark_parallel_tasks.py hi          # one language
venv/bin/python load_benchmark_parallel_tasks.py hi bn ta    # a subset
BATCH_SIZE=250 venv/bin/python load_benchmark_parallel_tasks.py hi
```

- `description = "benchmark_parallel_<lang>_batch<n> — <LanguageName>"`. The name
  token is the batch key; the language name is what the admin dashboard groups by.
- **The English source is attached to every item** so the annotation UI can show it.
  The loader indexes `en.jsonl` by `id`, resolves each item's `source_id`, and
  appends three keys — everything else is stored byte-for-byte unchanged:

  | Key | Value |
  |---|---|
  | `_ref_source_lang` | `"en"` |
  | `_ref_source_raw_text` | the English source `raw_text` |
  | `_ref_source_spoken_form` | the English source `spoken_form` |

  The `_ref_` prefix is the contract: **every exporter strips `_ref_*`**, so the
  round-trip stays lossless.
- **Validated on load:** duplicate item ids within a language abort the run (they
  would collide in the per-item rating lookup), and any `source_id` that does not
  resolve is reported as a warning.
- **Idempotent:** a re-run matches an existing batch by its
  `benchmark_parallel_<lang>_batch<n>` token and updates it in place. Never duplicates.
- Test ids come from SQLite autoincrement (no `max(id)+1` race).

### Loaded batches

| Lang | Items | Batches | Test IDs |
|------|-------|---------|----------|
| bn | 761 | 4 | 20994–20997 |
| en | 770 | 4 | 20998–21001 |
| gu | 744 | 4 | 21002–21005 |
| hi | 749 | 4 | 21006–21009 |
| kn | 729 | 4 | 21010–21013 |
| ml | 746 | 4 | 21014–21017 |
| mr | 765 | 4 | 21018–21021 |
| or | 613 | 4 | 21022–21025 |
| ta | 754 | 4 | 21026–21029 |
| te | 738 | 4 | 21030–21033 |
| ur | 764 | 4 | 21034–21037 |
| **Total** | **8133** | **44** | |

Batches are **unassigned** by default, so any annotator can open them. Assign them
from the admin dashboard to lock them to specific people.

---

## 3. Annotation UI

`frontend/src/components/BenchmarkVerification.vue`, dispatched by `test_type` in
`TestView.vue`, `DynamicTestView.vue` and `AdminTaskReview.vue`. The same component
serves both benchmark rounds.

### Reference panel (top of the page)

A collapsible panel that answers "what is this sentence for?" before the annotator
reads a word of it:

- **Phenomenon tags** as chips — the things this sentence exists to test.
- **English source** — the sentence this was translated from, in a highlighted
  callout, with its spoken form when it differs. Only shown when present, so round-1
  tasks simply don't render it.
- **Domain, suite, length bucket, quota class, target emotion, probes axes and
  source id** in a compact grid. The generator model is deliberately not shown —
  it is not something the annotator should be judging the sentence against.
- The header keeps the item id, language, domain and a tag count visible even when
  the panel is collapsed, and the open/closed state persists as you move between items.

### Editing and verdict

- **Raw Text** and **Spoken Form** are click-to-edit textareas that grow with content.
- Each field shows **Edited / Original**, a live char count, a **Reset**, and a
  **Compare** button that reveals the original value inline.
- **Accept / Reject**, then a **comment**. Quick-reason chips (Wrong translation,
  Unnatural phrasing, Spelling / typo, Number or unit wrong, Spoken form mismatch,
  Grammar, Wrong domain / tag) write a standard reason with one click.
- **A rejection cannot be submitted without a comment** — same rule as the
  audio-segmentation task. Accepts do not need one.
- Right-to-left rendering (Urdu) is automatic, including in the compare view.

### Shortcuts

`1` accept · `2` reject · `R` toggle reference · `Ctrl/⌘+Enter` submit & next ·
`Ctrl/⌘+S` save draft.

Saved drafts and completed items re-open exactly as left: `get_test` merges
`raw_text`, `spoken_form`, `decision` and `comments` back into each item, and sends
`original_raw_text` / `original_spoken_form` alongside so "Edited", **Reset** and
**Compare** still refer to the true original rather than the annotator's own edit.

---

## 4. Order, multi-annotator vs handoff

Identical to round 1 — see [BENCHMARK_TASKS.md §3b](BENCHMARK_TASKS.md). In short:

- Item order is **always** the original JSONL order; completed items are marked done
  in place, and an annotator resumes at the first item they haven't finished.
- `test.handoff_mode` **OFF (default)** = open: every annotator sees every item.
  **ON** = handoff: an assignee stops seeing items *another* annotator already
  completed, so a half-done batch can be handed over. Toggle it from
  `/admin/task/<id>`.

---

## 5. Admin review

`/admin/task/<test_id>` renders the same annotation UI, read-only and pre-filled,
with one tab per annotator plus a blank-task tab. Backed by
`GET /api/admin/task/<test_id>/annotations`. Read-only — an admin can never
overwrite an annotation from this page.

---

## 6. Exports

### 6a. JSONL — `export_benchmark_parallel_jsonl.py`

Every line is the **exact original object** (all fields, original key order,
including `domain`, `phenomenon_tags`, `probes_axes`, `quota_class`, `source_id`);
`_ref_*` and `completion_status` are stripped. For items an annotator **completed**:

| Field | Value |
|-------|-------|
| `qa_status` | `true` |
| `raw_text` | annotator's edited value |
| `spoken_form` | annotator's edited value |
| `decision` | `"accept"` or `"reject"` |
| `comment` | annotator's comment (only when non-empty) |

Items nobody completed are emitted unchanged (`qa_status` stays `"pending"`). If
several annotators rated an item, the **latest completed** submission wins.

```bash
cd /root/saffron/backend
venv/bin/python export_benchmark_parallel_jsonl.py --test-id 21006 out.jsonl
venv/bin/python export_benchmark_parallel_jsonl.py --lang hi hi.jsonl
venv/bin/python export_benchmark_parallel_jsonl.py --all exported/
# with a domain / phenomenon-tag accept-reject breakdown
venv/bin/python export_benchmark_parallel_jsonl.py --all exported/ --summary exported/summary.json
```

Every run prints an annotation summary (overall, per domain, per phenomenon tag);
`--summary` writes the same breakdown as JSON, also split by language.

> **Verified 2026-07-25:** a no-annotation export of all 11 languages round-trips
> the input exactly — same objects, same key order, all 8133 items. (The bytes
> differ only because the export writes real Unicode where the input used `\uXXXX`
> escapes, which is what the round-1 exporter does too.)

### 6b. Excel — `export_benchmark_excel.py`

The review-ready workbook: original and corrected side by side, every reference
field, and every comment — including comments on drafts and skips that never reach
the JSONL.

```bash
venv/bin/python export_benchmark_excel.py --test-id 21006 out.xlsx
venv/bin/python export_benchmark_excel.py --lang hi hi.xlsx
venv/bin/python export_benchmark_excel.py --all exported/          # <lang>.xlsx + all_languages.xlsx
venv/bin/python export_benchmark_excel.py --round v1 --all v1/     # the first round instead
venv/bin/python export_benchmark_excel.py --round all --lang hi both.xlsx
```

| Sheet | Contents |
|---|---|
| **Overview** | Totals, accept/reject/edit rates, and a guide to the other sheets. |
| **Annotations** | One row per item, 31 columns: batch, language, item id, source id, suite, domain, phenomenon tags, probes axes, quota class, length bucket, target emotion, **English raw text + spoken form**, **original** raw text + spoken form, **corrected** raw text + spoken form, changed flags, decision, comment, QA status, annotator name/email, status, submitted at, time taken, other annotators who touched the item, and a deep link into Saffron. Decisions are colour-coded and edited cells highlighted. |
| **All Submissions** | One row per *(item, annotator)* — every submission including `saved` drafts and `skipped` items, each with its own comment and text, and a flag for which one is the latest completed. Nothing is lost when two annotators disagree. |
| **Rejections** | Rejected items only, with comments. The triage sheet. |
| **Edits** | Only items whose text was actually changed, before and after. |
| **By Domain** / **By Phenomenon** / **By Language** | Items, annotated, accepted, rejected, accept %, reject %, raw/spoken edits, coverage % — with a TOTAL row. |
| **By Annotator** | Completed / saved / skipped, accept-reject split, accept %, items edited, comments written, average seconds per item, languages worked. |

All sheets have frozen headers and autofilters.

### 6c. Per-task CSV from the admin dashboard

`GET /api/admin/export_csv/<test_id>` (the download button on a task) now has a real
benchmark branch. It previously fell through to a generic case that emitted **empty**
text columns for benchmark tasks. It now exports language, suite, domain, phenomenon
tags, probes axes, quota class, length bucket, target emotion, source id, the English
source, original vs corrected raw text and spoken form with changed flags, the
decision and the comment — one row per submission, optionally filtered by `rater_id`.

---

## 7. Deploying changes

```bash
# frontend (served by Caddy from dist/)
cd /root/saffron/frontend && npm run build

# backend — graceful reload of the gunicorn master (no downtime, no dropped work)
kill -HUP $(pgrep -f 'gunicorn.*4020' | head -1)
```

Backend serves on `127.0.0.1:4020` (Caddy proxies `/api*`); 1 master + 6 workers,
run from the `saffron` tmux session via `backend/start_saffron.sh`.
