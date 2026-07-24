# Pipeline Examples — Real Use Cases

Copy-paste recipes for the situations that actually come up. Server commands
run on `tts-labelstudio`; PowerShell commands run on your laptop.

```bash
PY=/root/saffron/backend/venv/bin/python     # server shorthand used below
```

---

## Use case 1 — "Telugu version 5 rating is done, I need the docs"

One command on your laptop:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5
```

Docs appear in `C:\Users\Avnish\Downloads\saffron_docs\Telugu\<Persona>\`,
numbered after the last set already on Drive. Drag-drop the persona folders
into the Drive docs folder. Done.

---

## Use case 2 — "Now make the recording Excels from those docs"

Easiest: name the set directly and let the server fetch the docx from the
conversation-docs Drive folder (falls back to the server's own
`exports/auto_docs` copy if that set was never uploaded to Drive):

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 -l telugu -p storyteller -s 3
```

Or feed it a server path — the `saffron_docs.ps1` run printed a line like
`RUN_DOCX_DIR=/root/saffron/backend/exports/auto_docs/telugu_version_5_.../docx`:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_excels.ps1 /root/saffron/backend/exports/auto_docs/telugu_version_5_XXX/docx
```

Either way, Excels appear in `Downloads\saffron_docs\excels\Telugu\` named
`Telugu_<Persona>_Set<n>.xlsx` (numbering continues from the Excel Drive
folder — independent of the docx set numbers; `excel_sets_state.csv` on the
server is updated automatically). IDs inside use the two-letter
language prefix: `Te_Conv_1_T_1`. Upload to the Excel Drive folder.

---

## Use case 3 — "Voice actors uploaded recordings + Excel to Drive"

Load them as an audio segmentation set in one command (server):

```bash
$PY /root/saffron/backend/load_audio_set.py --link "https://drive.google.com/drive/folders/XXXX"
```

Downloads into the next free `setN`, fixes "Copy of " names, validates
WAV↔Excel ID matching, loads into the DB. Not sure about the folder contents?
Add `--no-load` first, then load later with
`$PY load_audio_segmentation_tasks.py setN`.

---

## Use case 4 — "What would run, without actually running it?"

```bash
$PY /root/saffron/backend/export_upload_docs.py -l odia -v new --dry-run
```

Shows the matched tests and the next set number per persona (CSV + live Drive
check), touches nothing.

---

## Use case 5 — "I only need the Storyteller docs re-done"

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5 -ExtraArgs "--personas storyteller"
```

---

## Use case 6 — "I want ALL conversations, including rejected and commented"

By default only accepted, comment-free conversations are exported. Override:

```powershell
powershell -ExecutionPolicy Bypass -File C:\Users\Avnish\saffron_docs.ps1 telugu 5 -ExtraArgs "--include-all --any-comments"
```

(`--include-all` = also rejected/unrated; `--any-comments` = keep commented ones.)

---

## Use case 7 — "The set-number CSVs look wrong / I deleted generated files"

Reset either CSV to exactly what is on Drive right now (server):

```bash
$PY /root/saffron/backend/export_upload_docs.py --sync-state   # docs CSV
$PY /root/saffron/backend/docx_to_excel.py --sync-state        # excel CSV
```

Careful: this makes the CSV mirror Drive EXACTLY, so counts for sets that were
generated on the server but not yet uploaded to Drive are dropped (a CSV being
ahead of Drive is normal and correct — numbering uses max(CSV, Drive)). Only
sync after everything generated has actually been uploaded. Numbering also
live-checks Drive on every run, so a stale CSV can never cause an overwrite.

---

## Use case 8 — "How are the MOS ratings coming along?"

No command needed — it's live, recomputed from the Label Studio DB every
minute: https://tts-labelstudio-dashboard.ai4bharat.org/mos
(Scripted projects show each annotator side by side with the disagreement
spread; Initial projects show the single-annotator ranking.)

---

## Use case 9 — "Automatic Drive upload instead of drag-drop" (one-time setup)

1. Google Cloud Console → create a service account → download JSON key,
   enable the Drive API.
2. Copy the key to `/root/saffron/backend/config/gdrive_service_account.json`.
3. Share the Drive docs folder with the service account email as Editor.
4. Then drop `--no-upload`; the server uploads directly, skips existing files:

```bash
$PY /root/saffron/backend/export_upload_docs.py -l telugu -v 5
```
