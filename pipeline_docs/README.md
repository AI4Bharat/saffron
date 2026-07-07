# Saffron Pipelines — Cheat Sheet

Everything runs on this server with the backend venv python:

```bash
PY=/root/saffron/backend/venv/bin/python
cd /root/saffron/backend
```

---

## 1. Conversation Pipeline (export → DOCX → Drive)

One command does it all: finds the tests for a language+version, exports the
**accepted, comment-free** conversations, builds `<Lang>_<Persona>_SetN.docx`
files (max 30 conversations per set, numbering continues from the last set on
Drive/CSV), arranged in an upload-ready `Language/Persona/` folder tree.

### The only command you normally need (run on your laptop)

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5
```

- 1st arg language: `hindi kannada marathi odia tamil telugu english`
- 2nd arg version: `2`..`5`, `new` (= "New Version"), `base` (= no version suffix)

This generates the docs on the server AND automatically transfers them to
`C:\Users\Avnish\Downloads\saffron_docs\<Language>\<Persona>\` (folders are
created if absent). Drag-drop the language folder contents into the Drive
folder — filenames and subfolders already match, nothing gets overwritten.

Pass extra flags with e.g. `-ExtraArgs "--personas storyteller"`.

Server-only alternative (no transfer): run on the server
`$PY export_upload_docs.py -l telugu -v 5 --no-upload` — it prints the
output folder and the scp command to pull it later.

### Other useful forms

```bash
$PY export_upload_docs.py -l telugu -v 5 --dry-run          # plan only: which tests, next set numbers
$PY export_upload_docs.py -l odia -v new --no-upload        # "New Version" campaign
$PY export_upload_docs.py -l telugu -v 5 --personas storyteller,relatable_peer --no-upload
$PY export_upload_docs.py -l telugu -v 5 --include-all --no-upload    # also rejected + unrated
$PY export_upload_docs.py -l telugu -v 5 --any-comments --no-upload   # include commented convs too
$PY export_upload_docs.py --sync-state                      # re-sync the set-number CSV from Drive
```

### Set-number tracking

- CSV: `/root/saffron/backend/upload_sets_state.csv` (language, persona, last_set).
- Updated automatically after every generation/upload.
- Every run also live-checks the Drive folder, and uses whichever is higher —
  so numbering never collides even if the CSV is stale.
- After manually uploading docs to Drive you don't need to do anything;
  `--sync-state` any time re-reads the truth from Drive.

### Direct (automatic) Drive upload — optional

Drop a Google service-account JSON key at
`config/gdrive_service_account.json`, share the Drive folder with the service
account email as Editor, then simply omit `--no-upload`:

```bash
$PY export_upload_docs.py -l telugu -v 5
```

It uploads into `<Language>/<Persona>/` on Drive, skips (never overwrites)
existing files, and updates the CSV.

---

## 2. DOCX → Recording Excel Pipeline (docx_to_excel.py)

Converts conversation DOCX sets into recording Excels with two sheets —
"Turns" (`ID | Speaker | Dialogue`, IDs like `Te_Conv_1_T_1`, two-letter
language **prefix**) and "Conversations" (`ID | Conversation`, IDs like
`Te_Conv_1`).

### One command from your laptop (converts on server + pulls here)

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 <server_docx_path>
```

The path can be a single .docx, a folder of docx, or a .zip — e.g. the docx
folder printed by a `saffron_docs.ps1` run. Excels land in
`C:\Users\Avnish\Downloads\saffron_docs\excels\<Language>\`.

- Output naming `<Language>_<Persona>_Set<n>.xlsx` continues from the last set
  in the Excel Drive folder
  (https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD),
  tracked in `backend/excel_sets_state.csv` + live Drive listing — same
  mechanism as the docs. Numbering is independent of the source docx set
  numbers.
- On the server directly: `$PY docx_to_excel.py <docx|folder|zip>`; reset the
  CSV from Drive with `$PY docx_to_excel.py --sync-state`.

---

## 3. Audio Segmentation Pipeline (Drive → server → DB)

One command downloads a Drive folder (WAVs + one Excel), fixes "Copy of "
names, validates WAV↔Excel ID matching, and loads the tasks into the DB:

```bash
$PY load_audio_set.py --link "https://drive.google.com/drive/folders/XXXX"
```

- Picks the next free `setN` directory automatically (use `--set set7` to pick one yourself).
- The Drive link must be shared as "Anyone with the link".
- Excel must have `ID`, `Speaker`, `Dialogue` columns and be named like
  `English_Calm_Explainer_Set3.xlsx` (language/persona come from the name).

### Other useful forms

```bash
$PY load_audio_set.py --link "..." --no-load          # download + validate only, load later
$PY load_audio_set.py --set set3 --skip-download      # validate + load an already-downloaded set
```

### Export audio segmentation results

```bash
$PY export_all_results.py     # bulk export of all rated results -> exports/*.jsonl
```

---

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
