# Saffron — Complete Architecture & Logic Reference

Saffron is AI4Bharat's in-house annotation platform. Annotators log in, open a task
assigned to them, work through its items one at a time, and submit a verdict and/or a
correction per item. Admins load tasks from JSONL, assign them, watch progress, review
what was submitted, message annotators, and export everything.

This document explains every moving part: the data model, the request lifecycle, all
six task types, assignment and locking, the admin surface, every export path, the
loader/exporter scripts, deployment, and the non-obvious invariants that hold the
whole thing together.

---

## 1. Stack and layout

**Backend** — Flask 3 + Flask-SQLAlchemy, JWT auth (PyJWT), Flask-Caching
(filesystem, `/tmp/flask-cache`), rotating log to `error.log`. Served by gunicorn
(1 master + 6 sync workers) on `127.0.0.1:4020`, behind Caddy.

**Frontend** — Vue 3 (`<script setup>` Composition API), Vite, Vue Router,
Bootstrap 5 + Bootstrap Icons. Built to `frontend/dist/`, served statically by Caddy,
which proxies `/api*` to gunicorn.

**Database** — SQLite at `backend/instance/database.db` (~1.1 GB). The models are
Postgres-compatible; nothing depends on SQLite specifics except that ids come from
`AUTOINCREMENT`.

```
saffron/
├── backend/
│   ├── main.py                     # app factory, config, one long-lived app context
│   ├── application/
│   │   ├── database.py             # the SQLAlchemy db object
│   │   ├── models.py               # 7 tables (see §2)
│   │   └── views.py                # ~2750 lines: every API route
│   ├── admin_reports.py            # CSV report builders used by the admin exports
│   ├── load_*.py                   # one loader per task type (JSONL -> Test rows)
│   ├── export_*.py                 # one exporter per task type (Test+Rating -> files)
│   ├── benchmark_tasks/            # round-1 benchmark input JSONL
│   ├── benchmark_tasks_new/        # round-2 (parallel) benchmark input JSONL
│   ├── conversation_tasks/, conversation_editable_tasks/, audio_segmentation/
│   ├── instance/database.db        # THE real database
│   └── venv/
└── frontend/src/
    ├── router/index.js             # routes + the auth/admin navigation guard
    ├── views/                      # page-level components
    │   ├── LoginView, SignupView, HomeView, CompletionView
    │   ├── TestView                # the annotator's task page (logged-in flow)
    │   ├── DynamicTestView         # the Prolific flow (session-based, no login)
    │   ├── TrackingPageView        # the admin dashboard (~2900 lines)
    │   └── AdminTaskReview         # read-only per-annotator review of one task
    └── components/                 # one component per task type + ConsentForm, GroundingPage
```

---

## 2. Data model (`application/models.py`)

| Table | Purpose |
|---|---|
| **Rater** | An annotator. `name` (the login username), `email`, `password` (plaintext — see §12), `age`, `gender`, `assigned_tasks` (a comma-separated string of Test ids), `is_active`, `prev_assigned_tasks`. |
| **Test** | One **batch** of work. `test_type` (dispatch key), `description` (carries the batch name and language), `json_entry` (a JSON **list of items** — the whole batch), `handoff_mode`. |
| **Rating** | One annotator's submission **for one item**. `rater_id`, `test_id`, `results_json`, `time_of_submission`, `time_taken_to_submit`, `page_no_progress` (**the item id, as a string**), `completion_status` (`completed` / `saved` / `skipped`). |
| **Study / Session** | Prolific integration: a Study maps a Prolific study id to a Test + completion URL; a Session maps a Prolific participant to a Study. |
| **Consent** | Records that a rater consented to a test (Prolific flow). |
| **Message** | Admin → annotator messages. `body`, `category` (`message` / `nudge` / `broadcast`), `is_read`, `broadcast_id` (shared across the fan-out rows of one broadcast), `edited_at`. |

### The three invariants everything depends on

1. **A Test is a batch, not a task.** `Test.json_entry` is a list; each element is an
   *item* with a unique `id`. The UI paginates through that list.
2. **`Rating.page_no_progress` is the item id.** Despite the name it is not a page
   number — it's `str(item['id'])`. Every merge, resume, progress count and export
   joins on it. One `(rater_id, test_id, page_no_progress)` triple = one Rating row,
   updated in place on re-submit.
3. **Item ids must be unique within a batch.** Two items sharing an id would share a
   Rating. The benchmark loaders now assert this at load time.

Schema drift is handled at startup: `main.py` issues best-effort `ALTER TABLE ... ADD
COLUMN` statements for the columns added over time (`completion_status`,
`assigned_tasks`, `is_active`, `prev_assigned_tasks`, `broadcast_id`, `edited_at`,
`handoff_mode`) and prints "may already exist" when they're there. That's why every
script run starts with those lines — they are informational, not errors.

---

## 3. Authentication

- `POST /api/login` with `{username, password}`. A Rater matches by `name` and a
  plaintext password compare; **`admin`** is not a Rater row — it matches the
  `ADMIN_PASSWORD` env var. Deactivated raters (`is_active = False`) are refused
  with 403. Returns a JWT (`HS256`, `JWT_SECRET_KEY`) carrying `username`.
- `POST /api/signup` requires the **daily signup PIN** — an 8-digit code in
  `backend/signup_key.txt` as `YYYY-MM-DD PIN`, rotated per day, readable by the
  admin at `GET /api/admin/signup-key`.
- Every protected route is wrapped in `@token_required`, which decodes the bearer
  token and passes `current_user` (the username) as the first argument. **Admin-only
  routes then check `current_user != "admin"` explicitly** — the decorator does not
  do it for you.
- The frontend stores the JWT in `localStorage.authToken`. `router.beforeEach`
  guards `/tracking` and `/admin/*` by decoding the payload client-side and checking
  `username === 'admin'`; that's a UX guard only — the real check is server-side.
- Deep links survive login: a guarded navigation redirects to
  `/login?redirect=<fullPath>`.

---

## 4. The annotation lifecycle

### 4.1 Loading work in — `GET /api/test/<test_id>`

This one function decides what an annotator sees, and it does five things in order:

1. **Resolve the rater.** Admin has no Rater row, so it borrows `Rater.query.first()`
   purely to satisfy the foreign key — and is then given `ratings = []`, so an admin
   previewing a task never sees anyone else's saved work.
2. **Assignment lock.** If the task is not in *this* rater's `assigned_tasks` and it
   *is* in someone else's, return **403 "locked to another annotator"**. A task
   assigned to nobody stays open to everyone (legacy behaviour, still relied on).
3. **Handoff filter.** If `test.handoff_mode` is ON *and* the task is assigned to this
   rater, drop items **another** rater already `completed`. Skips are not dropped —
   a skip is still open work. `handoff_mode` OFF (default) hides nothing, so several
   annotators can independently annotate the same batch.
4. **Order.** Always the original `json_entry` order. Nothing is ever re-sorted
   done-first — a batch looks the same on every visit.
5. **Merge.** For each item, overlay this rater's latest Rating: `completion_status`
   plus whichever result keys apply to the task type (`pre_scene`, `post_scene`,
   `text`, `evaluation`, `comments`, `transcript`, `rejection_reasons`,
   `custom_rejection_reason`, `raw_text`, `spoken_form`, `decision`, and turn-level
   dialogue merges). Because `raw_text`/`spoken_form` get overwritten by the
   annotator's edit, the response also carries **`original_raw_text` /
   `original_spoken_form`** so the UI can still tell edited from original.

Finally `page_no` is the index of the first item this rater hasn't `completed` or
`skipped` — the resume point (or one past the end when the batch is done).

### 4.2 Submitting — `POST /api/ratings`

Body: `{test_id, results_json, time_taken_to_submit, pageNo_progress, completion_status}`.

The server re-checks the assignment lock, stamps `results_json` with `test_id`,
`rater_email`, `time`, `time_taken` (ms ÷ 1000) and `data_id`, then **upserts** on
`(rater_id, test_id, page_no_progress)` — so re-submitting an item overwrites that
rater's row rather than piling up duplicates.

`completion_status` is the whole state machine:

| Status | Meaning | Counts as progress? | Exported? |
|---|---|---|---|
| `completed` | Submitted | yes | yes |
| `saved` | Draft — "Save Draft" | no | no (but appears in the Excel *All Submissions* sheet) |
| `skipped` | Deliberately passed over | yes, for resume | no |

`time_taken_to_submit` is stored in **milliseconds** (every component sends a
`Date.now()` delta). Every report divides by 1000.

A `teardown_request` hook rolls back a failed session — `main.py` keeps one app
context pushed forever, so without it one bad flush would poison a worker for every
later request.

---

## 5. The six task types

`test_type` is the single dispatch key. The frontend maps it to a component in three
places (`TestView`, `DynamicTestView`, `AdminTaskReview`); the backend branches on it
in `get_test`'s merge and in `export_csv`. Adding a type means touching those.

| `test_type` | Component | What the annotator does |
|---|---|---|
| `translation-correction` | `TranslationCorrection.vue` | Corrects a translated dialogue turn by turn, plus pre/post-scene text. Inline LaTeX editing with a live math preview. |
| `sentence-correction` | `SentenceCorrection.vue` | Corrects one translated sentence against its English source. |
| `conversation-evaluation` | `ConversationEvaluation.vue` | Accept/reject a whole dialogue, with comments. |
| `conversation-editable` | `ConversationEvaluation.vue` | Same UI, but turns are editable. |
| `audio-segmentation` | `AudioSegmentation.vue` | Plays a clip, corrects the transcript, accepts or rejects with structured rejection reasons. A comment is required on reject. |
| `benchmark-verification` | `BenchmarkVerification.vue` | Round-1 benchmark: verify `raw_text` + `spoken_form`, accept/reject. |
| `benchmark-parallel` | `BenchmarkVerification.vue` | Round-2 parallel benchmark — same UI, plus the English source sentence as reference. See [BENCHMARK_PARALLEL_TASKS.md](BENCHMARK_PARALLEL_TASKS.md). |

Every task component follows the same contract:

- **Props:** `currentTest` (the item), `test_id`, `currentIndex`, `isLastTest`,
  `session_id`, `readonly`.
- **Emits:** `next`, `prev`, `submit-status`.
- **Actions:** Save Draft (`saved`), Skip (`skipped`), Submit & Next (`completed`).
- **`readonly` defaults to `false`**, so the annotator experience is untouched; when
  the admin review page passes `true`, action buttons disappear and every
  submit/save/skip path returns early. An admin can never overwrite an annotation.

### The two annotator shells

- **`TestView.vue`** — the logged-in flow at `/:id`. Sidebar task explorer with
  search and per-item status, a progress bar, and deep-linking via `?task=<item_id>`.
  Changing item always scrolls the page to top and the sidebar to the active item
  (scrolling only the sidebar container, never the page's ancestors).
- **`DynamicTestView.vue`** — the Prolific flow at `/test?PROLIFIC_PID=…&STUDY_ID=…&SESSION_ID=…`.
  Consent form → task → completion redirect to the Prolific completion URL.

---

## 6. Assignment, locking, handoff

- `Rater.assigned_tasks` is a comma-separated, de-duplicated, order-preserving string
  of Test ids, set by `POST /api/admin/rater/<id>/assign_tasks`.
- **Locking:** a task assigned to anyone is visible only to them (403 for everyone
  else), enforced in both `get_test` and `create_rating`. Unassigned tasks are open.
- **`GET /api/rater/tasks`** returns the annotator's assigned tasks *in assignment
  order*, each with an inferred language, completed/total counts and a status
  (Not Started / In Progress / Completed). This drives `HomeView`.
- **Handoff mode** (`test.handoff_mode`, toggled by
  `POST /api/admin/task/<id>/handoff`) is how a half-done batch is passed on:
  turn it ON, unassign A, assign B, and B sees only what A didn't complete. Both
  annotators' work lands in the export; `get_test` only ever *hides* items, it never
  edits or deletes a Rating.
- **Deactivation** (`POST /api/admin/rater/<id>/deactivate`) is fully reversible: it
  stashes `assigned_tasks` into `prev_assigned_tasks`, clears `assigned_tasks`
  (freeing those locked batches), and blocks login. Reactivate restores it. No Rating
  is ever touched.

---

## 7. The admin surface

### 7.1 Dashboard — `GET /api/admin/dashboard` → `TrackingPageView.vue`

One large aggregate response, built by walking every Test and its Ratings:

- **By language** — test count, total tasks, unique completed, submissions. Language
  is inferred from the description first (matching against the 11 language names),
  falling back to the first item's `target_language` / `language` / `metadata.language`.
- **By task type** — a sub-tab per `test_type` with per-batch rows (id, description,
  language, totals, accepted/rejected, status: Complete / In progress / Not started),
  searchable, filterable by language and status, sortable, paginated, expandable.
  **New task types appear automatically** — nothing is hard-coded.
- **Audio-segmentation specifics** — per-set language/persona stats, audio seconds
  completed, and per-voice-artist rejection rollups.
- **Annotators** — activity, current/last task, throughput.

Clicking any task opens `/admin/task/<id>`.

### 7.2 Task review — `GET /api/admin/task/<id>/annotations` → `AdminTaskReview.vue`

Returns the task's items plus, per annotator, their latest submission per item with
status, normalised verdict and counts. The page renders **the same task component**
the annotator used, `readonly`, pre-filled:

- One tab per annotator, plus a **Blank task** tab (shown by default when nobody has
  submitted yet) and an **Open fresh empty page** button.
- A **Handoff mode** switch (top right).
- The verdict is normalised across task types: `results.decision` (benchmark) or
  `results.evaluation` (conversation/audio).

### 7.3 Messaging

Admin → annotator, purely additive, never mutating other tables:

| Route | Purpose |
|---|---|
| `POST /api/admin/rater/<id>/message` | One annotator. |
| `POST /api/admin/message/broadcast` | Fan out one row per annotator, all sharing a `broadcast_id`. |
| `PUT /api/admin/message/<id>` / `PUT /api/admin/broadcast/<bid>` | Edit after sending; stamps `edited_at`. |
| `POST /api/admin/rater/<id>/nudge` | A canned "please continue" message. |
| `GET /api/admin/messages` | The admin's sent-message outbox. |
| `GET /api/rater/messages`, `POST /api/rater/messages/read` | The annotator's inbox. |

---

## 8. Exports

Three layers, deliberately separate.

### 8.1 In-app CSV (admin dashboard buttons)

| Route | What it gives you |
|---|---|
| `GET /api/admin/export_csv/<test_id>` | Every submission for one task, one row per (item, annotator), with **task-type-specific columns**. Optional `?rater_id=`. |
| `GET /api/admin/export_tasks_csv` | The task inventory (Sr. No. per language, language, task id, detail, item count), filterable by `test_type` / `version`. |
| `GET /api/admin/export_annotators_csv` | Per-annotator summary, date-filterable. |
| `GET /api/admin/export_rater_ratings_csv/<rater_id>` | One annotator's detailed ratings. |
| `GET /api/admin/export_all_ratings_csv` | Every annotator's detailed ratings. |
| `GET /api/admin/export_audio_clips_csv` | Clip-level audio-segmentation rows with a playable deep link; `?only_rejected=`. |
| `GET /api/admin/export_artist_report_csv` | Per-voice-artist rejection report. |

The row builders live in `admin_reports.py`. All CSVs are UTF-8 with a BOM so Excel
opens Indic text correctly.

### 8.2 JSONL round-trip exporters (scripts)

One per family — `export_jsonl.py`, `export_conversations.py`,
`export_benchmark_jsonl.py`, `export_benchmark_parallel_jsonl.py`. The contract is
always the same: **emit the exact original object**, merging in only the annotation
fields, so an un-annotated export is byte-identical in content to the input. Items
nobody completed come out untouched; when several annotators rated one item, the
**latest completed** wins.

### 8.3 Excel — `export_benchmark_excel.py`

The review workbook for both benchmark rounds: original vs corrected side by side,
all reference metadata, every comment (drafts and skips included), plus rejection,
edit, per-domain, per-phenomenon, per-language and per-annotator sheets. Full column
list in [BENCHMARK_PARALLEL_TASKS.md §6b](BENCHMARK_PARALLEL_TASKS.md).

`backup_db_to_excel.py` / `restore_db_from_excel.py` dump and restore the whole DB —
this is what recovered the 2026-07-10 LaTeX corruption.

---

## 9. Loader scripts

Every loader follows the same shape: read `<lang>.jsonl` → chunk into batches → one
`Test` per batch with a name token in the description → **idempotent update in place**
on re-run, matched by that token.

| Script | Loads |
|---|---|
| `load_jsonl.py` | translation-correction |
| `load_sentences.py` | sentence-correction |
| `load_conversation_tasks.py` | conversation-evaluation |
| `load_conversation_editable_tasks.py` | conversation-editable |
| `load_audio_segmentation_tasks.py`, `load_audio_set.py` | audio-segmentation |
| `load_benchmark_tasks.py` | benchmark-verification (round 1) |
| `load_benchmark_parallel_tasks.py` | benchmark-parallel (round 2) |

**Ids always come from SQLite autoincrement.** Every loader used to do `max(id)+1`,
which raced under concurrent runs and silently overwrote rows; that was removed
everywhere on 2026-07-23.

Other operational scripts: `delete_tasks.py`, `delete_raters.py`, `db_clear.py`,
`summarize_db.py`, `export_db_summary_csv.py`, `sync_all_state.py`,
`generate_docs.py` / `export_upload_docs.py` (DOCX generation + Drive upload),
`docx_to_excel.py`, `transliterate_conversations.py`, `fix_latex_recovery.py`.

> `fix_database_escapes.py` is renamed `.BROKEN_DO_NOT_RUN` — it corrupted LaTeX in
> the DB on 2026-07-10. Do not resurrect it; see `fix_database_escapes.README`.

---

## 10. Deployment

```bash
# frontend
cd /root/saffron/frontend && npm run build         # -> dist/, served by Caddy

# backend: graceful reload (workers finish in-flight requests first)
kill -HUP $(pgrep -f 'gunicorn.*4020' | head -1)

# full restart (only if the master itself must be replaced)
tmux kill-session -t saffron 2>/dev/null
tmux new-session -d -s saffron \
  'bash /root/saffron/backend/start_saffron.sh 2>&1 | tee -a /root/saffron/backend/gunicorn.log'
```

Config comes from `backend/.env`: `SECRET_KEY`, `DATABASE_URI`, `JWT_SECRET_KEY`,
`ADMIN_PASSWORD`. `DATABASE_URI` can be overridden per-process, which is the safe way
to test a script against a **copy** of the database:

```bash
cp instance/database.db /tmp/t/instance/database.db
DATABASE_URI='sqlite:////tmp/t/instance/database.db' venv/bin/python export_benchmark_excel.py --all /tmp/out
```

---

## 11. Invariants worth not breaking

1. `Rating.page_no_progress` is the **item id string**. Change it and every merge,
   resume, progress count and export breaks at once.
2. Item ids must be unique within a batch.
3. `json_entry` is stored as the **pristine source object**. Anything the app adds
   for display is prefixed `_ref_` and stripped by the exporters. Never mutate the
   stored item with annotation data — annotations live in Rating.
4. `get_test` may **hide** items (handoff) but must never edit or delete a Rating.
5. `readonly` defaults to `false` on every task component.
6. Item order is the original `json_entry` order, always.
7. `time_taken_to_submit` is milliseconds.
8. Loaders are idempotent and matched by their name token; ids come from autoincrement.

---

## 12. Known gaps

- **Passwords are stored in plaintext** (`Rater.password`, compared directly at
  login). This predates the current codebase and is the single most valuable thing to
  fix — it needs a hashing migration plus a one-off rehash of existing rows.
- `POST /api/prolific/rating` and the other Prolific write routes are unauthenticated
  by design (session-based), and `POST /api/test`, `GET /api/results*`,
  `GET /api/verify_test/<id>`, `GET /api/tracking` carry no auth decorator at all.
  They are only reachable behind Caddy, but they should be locked down.
- The dashboard aggregate walks every Test and Rating on each request (~2.7 s at the
  current data volume). It will need incremental aggregation or caching as data grows.

---

## 13. Recent changes (2026-07-25)

- **Round-2 parallel benchmark loaded** — `benchmark-parallel`, 44 batches, 8133
  items across 11 languages, Test ids 20994–21037, with the English source sentence
  attached to every item as `_ref_*` reference data.
- **New scripts** — `load_benchmark_parallel_tasks.py` (with `--dry-run` and
  duplicate-id validation), `export_benchmark_parallel_jsonl.py` (with a
  domain/phenomenon `--summary`), `export_benchmark_excel.py` (8-sheet workbook for
  both rounds).
- **UI** — reference panel (phenomenon tags, English source, full metadata grid),
  per-field Compare against the original, quick rejection-reason chips, a required
  comment on reject, and an `R` shortcut.
- **Bug fixes** —
  - `export_csv` had **no benchmark branch**, so per-task CSV downloads for benchmark
    tasks emitted empty text columns. Fixed with a full 19-column branch.
  - `export_csv` wrote raw **milliseconds** under a column headed "Time Taken
    (seconds)" — every value was 1000× too high. Now divided, matching every other report.
  - `PUT /api/ratings/<id>` was **completely unauthenticated** — anyone who could
    reach the API could overwrite any annotator's submission by id. Now requires a
    token and restricts edits to the rating's owner or an admin.
  - Resuming a benchmark draft showed the annotator's own edit as "Original", and
    **Reset** restored the edit instead of the true original, because the backend
    merges edits over `raw_text`/`spoken_form`. The pristine values are now sent
    alongside as `original_raw_text` / `original_spoken_form` (also in the admin
    review page).
  - Save/Skip could race with Submit (each guarded a different flag); all three now
    share one `isBusy` guard.
