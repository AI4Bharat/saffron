# Saffron Pipelines — Cheat Sheet

Everything runs on this server with the backend venv python:

```bash
PY=/root/saffron/backend/venv/bin/python
cd /root/saffron/backend
```

---

## 1. Conversation Pipeline (export → DOCX → Drive)

Builds `<Lang>_<Persona>_SetN.docx` files (max 30 conversations per set,
continuing set numbers from the last set on Drive/CSV), arranged in an
upload-ready `Language/Persona/` tree. By default only **accepted, comment-free**
conversations. Non-English is exported from the annotation DB; **English is read
straight from `conversation_editable_tasks/version_<n>/`** (it is not annotated).

### Range mode (recommended): language selector(s) + one END version

```powershell
# from the laptop:
powershell -File C:\Users\Avnish\saffron_docs.ps1 -AllLanguages -English -EndVersion 6
powershell -File C:\Users\Avnish\saffron_docs.ps1 -Languages "odia,hindi,telugu" -EndVersion 6
powershell -File C:\Users\Avnish\saffron_docs.ps1 -AllLanguages -EndVersion 6 -DryRun   # plan only
```
```bash
# on the server:
$PY export_upload_docs.py --all-languages --english --end-version 6 --no-upload
$PY export_upload_docs.py --languages odia,hindi,telugu --end-version 6 --dry-run
```

Each language generates versions `(its last uploaded + 1) .. end-version`, where
the last version per language is tracked in **`version_state.csv`** and advanced
automatically (to the highest version that actually produced docs). Selectors:
`--languages a,b,c`, `--all-languages` (hindi kannada marathi odia tamil telugu),
`--english`.

### Single mode: one language, one version

```powershell
powershell -File C:\Users\Avnish\saffron_docs.ps1 telugu 5
powershell -File C:\Users\Avnish\saffron_docs.ps1 odia new
```
```bash
$PY export_upload_docs.py -l telugu -v 5 --no-upload
$PY export_upload_docs.py -l odia -v new --dry-run
```
2nd arg version: `2`..`N`, `new` (= "New Version"), `base` (= no version suffix).

Docs are transferred to `C:\Users\Avnish\Downloads\saffron_docs\<Language>\<Persona>\`.
Pass extra flags with e.g. `-ExtraArgs "--personas storyteller"` (or `--include-all`,
`--any-comments`).

### Set + version tracking

- `upload_sets_state.csv` (language, persona, last_set) — updated automatically;
  numbering always uses `max(CSV, live Drive)` so it never collides. After a manual
  upload run `$PY export_upload_docs.py --sync-state` to mirror Drive.
- `version_state.csv` (language, last_version) — updated automatically on generate.
  Versions are NOT encoded on Drive, so this CSV is the source of truth; edit it by
  hand to correct a language's baseline.

### Direct (automatic) Drive upload — optional

Drop a Google service-account JSON key at `config/gdrive_service_account.json`,
share the Drive folder with the service account email as Editor, then omit
`--no-upload`. It uploads into `<Language>/<Persona>/`, never overwrites existing
files, and updates the CSVs.

## 2. DOCX → Recording Excel Pipeline (docx_to_excel.py)

Converts conversation DOCX sets into recording Excels with two sheets —
"Turns" (`ID | Speaker | Dialogue`, IDs like `Te_Conv_1_T_1`, two-letter
language **prefix**) and "Conversations" (`ID | Conversation`, IDs like
`Te_Conv_1`).

### One command from your laptop (converts on server + pulls here)

```powershell
# By Drive set (downloads the docx from the conversation-docs Drive folder):
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 -l telugu -p storyteller -s 3

# Or by server path (single .docx, folder of docx, or .zip):
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 <server_docx_path>
```

With `-l/-p/-s` the server fetches
`<Language>/<Persona>/<Language>_<Persona>_Set<n>.docx` from the
conversation-docs Drive folder
(https://drive.google.com/drive/folders/15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk);
if that set was generated on the server but never uploaded to Drive, it
automatically falls back to the copy in `backend/exports/auto_docs/*/docx`.
The path form is unchanged — e.g. the docx folder printed by a
`saffron_docs.ps1` run. Either way the Excels land in
`C:\Users\Avnish\Downloads\saffron_docs\excels\<Language>\`.

- Output naming `<Language>_<Persona>_Set<n>.xlsx` continues from the last set
  in the Excel Drive folder
  (https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD),
  tracked in `backend/excel_sets_state.csv` + live Drive listing — same
  mechanism as the docs. Numbering is independent of the source docx set
  numbers, and the CSV is updated automatically on every conversion.
- On the server directly: `$PY docx_to_excel.py <docx|folder|zip>` or
  `$PY docx_to_excel.py -l <language> -p <persona> -s <set>`; reset the
  CSV from Drive with `$PY docx_to_excel.py --sync-state`.
- Note on the state CSVs: both `excel_sets_state.csv` and
  `upload_sets_state.csv` may legitimately be AHEAD of their Drive folders —
  they also count sets generated on the server that were not uploaded yet
  (e.g. runs with `--no-upload`, or xlsx not yet placed in the Excel folder).
  Next-set numbering always uses max(CSV, Drive), so this never collides.
  Only run `--sync-state` if you want the CSV to mirror Drive exactly.

---

## 3. Audio Segmentation Pipeline (Drive → server → DB)

The voice actors' recordings live in a Drive folder that contains an
**`EXPORTED ID`** subfolder (per-turn conversation WAVs named like
`Conv_10_T_1_En.wav`) plus other things we ignore (e.g. `topic exported`).
The matching recording Excel lives in the shared Excel Drive folder under
`<Language>/<persona - actor>/<Language>_<Persona>_Set<n>.xlsx`.

### Two-source mode (recommended) — give the audio link + persona/set

```bash
$PY load_audio_set.py --audio-link "https://drive.google.com/drive/folders/XXXX" \
    --persona storyteller --excel-set 2            # --language defaults to english
```

It downloads **only** the `EXPORTED ID` WAVs (curl direct-download — robust
against gdown's "too many accesses" rate limit), renames
`Conv_10_T_1_En.wav → En_Conv_10_T_1.wav` so they match the Excel `ID`
column, pulls `<Language>_<Persona>_Set<n>.xlsx` from the shared Excel folder,
validates WAV↔Excel ID matching, picks the next free `audio_segmentation/setN/`,
and loads a `Test` (`test_type = audio-segmentation`).

- **Each set has its own audio folder.** Set numbering restarts per set, so the
  same `En_Conv_5_T_1` ID exists in every set with *different* dialogue — never
  point one audio folder at two different `--excel-set` values.
- From your laptop: `powershell -File C:\Users\Avnish\saffron_audio.ps1 -AudioLink "<...>" -Persona storyteller -ExcelSet 2`
- **All languages/sets:** WAV names are read from the Excel ID column (En/Hi/Te/Ta/Od/Gu/Ka/Ma...), so any prefix matches exactly; pass --language <lang> (default english).

### Single-folder mode (original) — one folder holds WAVs + one Excel

```bash
$PY load_audio_set.py --link "https://drive.google.com/drive/folders/XXXX"
```

### Common options

```bash
--set setN          # force the local set dir (default: next free setN)
--no-load           # download + validate only, load later
--skip-download     # validate + load an already-downloaded set dir
--id-subfolder STR  # WAV subfolder name in two-source mode (default "EXPORTED ID")
```

The Drive links must be shared as "Anyone with the link". The Excel must have
`ID`, `Speaker`, `Dialogue` columns and be named like
`English_Storyteller_Set2.xlsx` (language/persona come from the name).

### Export audio segmentation results

```bash
$PY export_all_results.py     # bulk export of all rated results -> exports/*.jsonl
```

## Where things live

| What | Where |
|---|---|
| Conversation runs (jsonl + docx) | `backend/exports/auto_docs/<lang>_<version>_<timestamp>/` |
| Excel runs | `backend/exports/excel_runs/run_<timestamp>/` |
| Docs set-number state CSV | `backend/upload_sets_state.csv` |
| Excel set-number state CSV | `backend/excel_sets_state.csv` |
| Excel Drive folder | https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD |
| Audio segmentation sets | `backend/audio_segmentation/setN/` |
| Drive docs folder | https://drive.google.com/drive/folders/15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk |
| Worked examples | [EXAMPLES.md](EXAMPLES.md) (same folder) |
| Full details | `CONVERSATION_PIPELINE_GUIDE.md`, `AUDIO_SEGMENTATION_GUIDE.md` (same folder) |
| Live MOS dashboard | https://tts-labelstudio-dashboard.ai4bharat.org/mos |
