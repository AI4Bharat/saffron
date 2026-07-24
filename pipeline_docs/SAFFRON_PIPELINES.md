# Saffron Pipelines — My Cheat Sheet

Everything runs here on **tts-labelstudio** (this VM). Three laptop launchers
(`C:\Users\Avnish\saffron_*.ps1`) wrap the server work and pull results to my PC.

> Server code: `/root/saffron/backend/`  ·  backend python: `PY=/root/saffron/backend/venv/bin/python`
> `cd /root/saffron/backend` first when running the server commands below.

---

## ⭐ Example runs (copy-paste)

### A) Doc task — conversations → DOCX sets (of 30) → my PC

**Range mode** — give language selector(s) + one END version; each language generates
from *its own* last uploaded version + 1 up to that end version (tracked in `version_state.csv`):

```powershell
# ALL non-English languages, catch every one up to version 6:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 -AllLanguages -EndVersion 6

# All non-English + English (English comes from its per-version JSONL dir, not the DB):
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 -AllLanguages -English -EndVersion 6

# Only some languages:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 -Languages "odia,hindi,telugu" -EndVersion 6

# English only:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 -English -EndVersion 6

# See the PLAN first (languages, versions, next set numbers) — generates nothing:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 -AllLanguages -English -EndVersion 6 -DryRun
```

**Single mode** — one language, one version (also handles `new` / `base`):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 odia new
# one persona only:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5 -ExtraArgs "--personas storyteller"
```

Docs land in `C:\Users\Avnish\Downloads\saffron_docs\<Language>\<Persona>\`, max 30 conversations/set,
ready to drag into Drive. **After uploading, run the sync** (see below) to lock in set numbers.

**On the VM directly:**
```bash
cd /root/saffron/backend
$PY export_upload_docs.py --all-languages --english --end-version 6 --no-upload
$PY export_upload_docs.py --languages odia,hindi,telugu --end-version 6 --dry-run
$PY export_upload_docs.py -l telugu -v 5 --no-upload
```

### B) Audio-segmentation task — recordings → DB (one set per audio folder)

```powershell
# Storyteller Set 1 and Set 2 — each has its OWN audio folder:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "https://drive.google.com/drive/folders/AAAA_set1" -Persona storyteller -ExcelSet 1
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "https://drive.google.com/drive/folders/BBBB_set2" -Persona storyteller -ExcelSet 2

# Calm Explainer Set 4:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "https://drive.google.com/drive/folders/CCCC" -Persona calm_explainer -ExcelSet 4

# Non-English (names come from the Excel's own IDs; just add -Language):
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "https://drive.google.com/drive/folders/EEEE" -Persona storyteller -ExcelSet 2 -Language telugu

# Download + validate only, no DB write:
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "https://drive.google.com/drive/folders/AAAA" -Persona storyteller -ExcelSet 1 -NoLoad
```

**On the VM directly:**
```bash
cd /root/saffron/backend
$PY load_audio_set.py --audio-link "https://drive.google.com/drive/folders/AAAA" --persona storyteller --excel-set 1
$PY load_audio_set.py --audio-link "https://drive.google.com/drive/folders/AAAA" --persona storyteller --excel-set 1 --no-load
$PY load_audio_set.py --link "https://drive.google.com/drive/folders/DDDD"     # old single-folder mode (WAVs+Excel together)
```

---

## 1. Conversation DOCX — details

### Selectors (range mode)
- `-Languages "odia,hindi,telugu"` — explicit list.
- `-AllLanguages` — every non-English language: `hindi kannada marathi odia tamil telugu`.
- `-English` — add English (or use alone). **English is special:** it is *not* annotated in
  saffron; its conversations are read straight from `conversation_editable_tasks/version_<n>/`
  (filtered to English). Every other language is exported from the annotation DB.
- `-EndVersion N` — required in range mode.

### How the range works
For each language, last uploaded version comes from **`version_state.csv`**; it generates versions
`last+1 .. EndVersion`. Example with `-AllLanguages -English -EndVersion 6` and
`version_state.csv` = english 5, odia/hindi/telugu 3:
- English → v6 · Odia/Hindi/Telugu → v4,v5,v6 · a language already ≥ 6 is skipped.
- `version_state.csv` is advanced automatically to the **highest version that actually produced docs**
  (so if v5 had no ready conversations yet, it won't jump past it).
- A language with no row in `version_state.csv` warns and starts at v2 — edit the CSV to set its baseline.

### Always
- Only **accepted, comment-free** conversations (non-English); English takes all source conversations.
- Sets of **max 30** conversations; **set numbers continue** from `max(upload_sets_state.csv, live Drive)`
  and never overwrite existing Drive files.
- Everything lands in ONE run dir arranged `<Language>/<Persona>/` → one clean pull to the laptop.
- Extra `-ExtraArgs`: `--personas storyteller,relatable_peer` · `--include-all` · `--any-comments`.

### After generating: upload + sync
1. Drag the `<Language>` folders into the Drive docs folder.
2. Sync set numbers from Drive (version numbers are already saved automatically):
   ```bash
   $PY export_upload_docs.py --sync-state
   ```

## 2. Recording Excel from DOCX

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 -l telugu -p storyteller -s 3
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 <server_docx_path>
```
Two sheets — **Turns** (`ID|Speaker|Dialogue`, IDs like `Te_Conv_1_T_1`) and **Conversations**
(`ID|Conversation`). Lands in `C:\Users\Avnish\Downloads\saffron_docs\excels\<Language>\`.
These are the same Excels the audio-seg loader pulls from.

## 3. Audio-Segmentation — details

The actors' recordings folder has an **`EXPORTED ID`** subfolder (per-turn WAVs `Conv_10_T_1_En.wav`)
plus other stuff we ignore (`topic exported`). The loader:
1. downloads **only** `EXPORTED ID` WAVs (curl direct-download — avoids gdown rate limits),
2. names each WAV from the Excel's own `ID` column, pulling `Conv_N_T_M` out of the audio filename,
3. pulls `<Language>_<Persona>_Set<ExcelSet>.xlsx` from the shared Excel folder,
4. validates WAV↔Excel ID matching, uses next free `audio_segmentation/setN/`, loads a `Test`.

Flags: `-Language english` (default) · `-Set setN` (force local dir) · `-NoLoad` (no DB write).

> **CRITICAL:** each set has its own audio folder. Set numbering restarts every set, so `En_Conv_5_T_1`
> exists in every set with **different dialogue** — never point one audio folder at two `--excel-set` values.

> **Language-robust:** WAV names come from the Excel `ID` column, so any prefix matches exactly —
> `En` english, `Hi` hindi, `Te` telugu, `Ta` tamil, `Od` odia, `Gu` gujarati, **`Ka` kannada**,
> **`Ma` marathi/malayalam** (= `language.title()[:2]`). Pass `-Language <lang>`.

### Undo / cleanup / inspect
```bash
cd /root/saffron/backend
rm -rf audio_segmentation/setN                # remove a downloaded set dir
$PY delete_tasks.py                           # interactive: delete a Test from the DB
$PY export_all_results.py                      # bulk export rated results -> exports/*.jsonl
$PY -c "from main import app; from application.models import Test; app.app_context().push(); [print(t.id, t.description) for t in Test.query.filter_by(test_type='audio-segmentation')]"
```

---

## Syncing state — one command

Sync **everything** in one shot (run it **after** you've uploaded the docs/excels to Drive):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_sync.ps1
```
```bash
# on the VM:
$PY sync_all_state.py
```

It runs: docx set numbers (`upload_sets_state.csv`) ← Drive, excel set numbers
(`excel_sets_state.csv`) ← Drive, and rebuilds the audio-seg manifest
(`audio_segmentation_state.csv`) from the DB. `version_state.csv` is left untouched
(versions aren't on Drive). Individual syncs still work if you want just one:
`$PY export_upload_docs.py --sync-state` / `$PY docx_to_excel.py --sync-state`.

> **Warning:** `--sync-state` makes a CSV mirror Drive **exactly**. If you have sets that were
> generated but not yet uploaded, upload them first — otherwise those set numbers get dropped
> and could be reused. (A CSV being *ahead* of Drive is the normal "pending upload" state.)

### The state CSVs (all under backend/)

| CSV | Tracks | Updated | Synced by `saffron_sync` |
|---|---|---|---|
| `upload_sets_state.csv` | last **doc set** per (language, persona) | on generate + sync | Yes (from Drive docs folder) |
| `excel_sets_state.csv` | last **excel set** per (language, persona) | on convert + sync | Yes (from Drive excel folder) |
| `audio_segmentation_state.csv` | loaded audio-seg Tests (id, lang, persona, set, task/wav counts) | on sync | Yes (rebuilt from the DB) |
| `version_state.csv` | last uploaded **version** per language | automatically on generate | **No** — edit by hand to fix a baseline |

Set numbering always uses `max(CSV, live Drive)`, so a CSV being ahead of Drive never collides.

## Drive folders

| What | Folder |
|---|---|
| Conversation docs | https://drive.google.com/drive/folders/15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk |
| Recording Excels  | https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD |
| Audio recordings  | per-batch links the actors share with me |

## Laptop launchers (only these live on my PC)

| Script | Does |
|---|---|
| `C:\Users\Avnish\saffron_docs.ps1`   | conversations → DOCX sets → my PC (range or single mode) |
| `C:\Users\Avnish\saffron_excels.ps1` | DOCX → recording Excel → my PC |
| `C:\Users\Avnish\saffron_audio.ps1`  | audio recordings + Excel → DB (audio-segmentation) |
| `C:\Users\Avnish\saffron_sync.ps1`   | sync all state CSVs (docs + excel from Drive, audio from DB) |

_This file lives on the VM at `/root/saffron/pipeline_docs/SAFFRON_PIPELINES.md`._
