# Saffron Conversation Annotation Pipeline Guide

This document outlines the step-by-step pipeline for loading conversation tasks (specifically including the editable ones), exporting rated annotations, and generating structured Microsoft Word (.docx) reports.

---

## 1. Load Tasks Into Database

When you have new conversation JSONL files, place them in the correct folder:
- **Root Directory**: `/root/saffron/backend/conversation_editable_tasks/` (or `conversation_editable_tasks/new_version` for custom/v2 campaigns).

### Commands

**Step A: Dry Run**
Inspect the naming format, auto-detected language, persona, grade bucket, and subfolder suffixes without making database edits:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/load_conversation_editable_tasks.py --dry-run
```

**Step B: Active Load**
Write the tasks to the backend database as `conversation-editable` test types:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/load_conversation_editable_tasks.py
```

### Advanced Loading Options
The script supports additional flags for batching, filtering by subfolders, and excluding languages:
* **`--batch-size <N>`**: Split each large JSONL file into smaller tests containing up to `N` tasks.
* **`--exclude-english`**: Exclude files containing `english` in their filename.
* **`--subfolder <folder_name>`**: Only load files located inside a specific subfolder (e.g. `version_5`).

#### Example: Batching non-English tasks from Version 5 (Sets of 100)
**Dry Run**:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/load_conversation_editable_tasks.py --dry-run --subfolder version_5 --exclude-english --batch-size 100
```
**Active Load**:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/load_conversation_editable_tasks.py --subfolder version_5 --exclude-english --batch-size 100
```

---

## 2. Export Rated/Edited Annotations

Once the annotators have evaluated and edited the conversations, you can export the results back into JSONL files.

### Configuration
Open [export_conversations.py](file:///root/saffron/backend/export_conversations.py#L14-L17) and configure your targeted test IDs and exports directory directly inside the code:
```python
TEST_IDS = [20098, 20099, 20100]  # List of Test IDs to export
OUTPUT_DIR = "/root/saffron/backend/exports"  # Output directory for exported JSONL files
```

### Commands

Depending on your data filtering needs, run the exporter using any of the options below:

- **Export Everything** (Accepted, Rejected, Unrated):
  ```bash
  /root/saffron/backend/venv/bin/python /root/saffron/backend/export_conversations.py
  ```

- **Export Only Accepted Ratings**:
  ```bash
  /root/saffron/backend/venv/bin/python /root/saffron/backend/export_conversations.py --only-accepted
  ```

- **Export Only Accepted Ratings WITHOUT Comments**:
  ```bash
  /root/saffron/backend/venv/bin/python /root/saffron/backend/export_conversations.py --only-accepted --without-comments
  ```

- **Export Ratings WITH Comments**:
  ```bash
  /root/saffron/backend/venv/bin/python /root/saffron/backend/export_conversations.py --with-comments
  ```

---

## 3. Generate Word Document (.docx) Reports

You can compile exported JSONL lines into structured Word documents split by persona (e.g. `calm_explainer`, `warm_encourager`, etc.) with cleaned inline LaTeX formulas.

### Configuration
Open [generate_docs.py](file:///root/saffron/backend/generate_docs.py) and configure your default set number at the top of the script:
```python
SET_NUMBER = 1  # Enter the set number here (e.g., 1 for Set1)
```

### Command Format
To generate DOCX reports for a single JSONL file or directory:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py <path_to_jsonl_or_dir> <output_docx_dir> [options]
```

### Options
- `--version` / `-v`: Filter input conversation files by version (e.g. `--version 3` or `--version new_version`).
- `--set` / `-s`: Override the set number appended to the filename (e.g. `--set 2` or `-s 2`).
- `--language` / `-l`: Target language to filter conversations (e.g. `--language telugu`).
- `--start-id`: Starting task ID to filter files (inclusive).
- `--end-id`: Ending task ID to filter files (inclusive).
- `--task-ids` / `-t`: Comma-separated list or range of task IDs (e.g. `20179-20186` or `20179,20180`).

### Examples

**Example A: Process a directory with version filtering**
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py /root/saffron/backend/conversation_editable_tasks /root/saffron/backend/exports/docx --version 3 --language telugu
```

**Example B: Override set number via command line**
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py /root/saffron/backend/conversation_tasks/conversations_telugu_warm_encourager_elementary.jsonl /root/saffron/backend/exports/docx --set 2 --language telugu
```

**Example C: Process all Odia files inside a directory at once**
You can compile all files for a specific language (e.g. Odia) in the directory at once by passing the input folder and filtering by language:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py /root/saffron/backend/conversation_editable_tasks /root/saffron/backend/exports/docx --language odia
```

**Example D: Bulk generate Odia files using a `for` loop command**
To loop over and process files containing `odia` inside the `exports/` folder individually:
```bash
for f in /root/saffron/backend/exports/*odia*.jsonl; do
  /root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py "$f" /root/saffron/backend/exports/docx --language odia
done
```

**Example E: Process Odia Set 1 using Task ID range filtering**
Extract and compile all exported Odia files belonging to the first set (IDs 20179 to 20186) as Set 1:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py /root/saffron/backend/exports /root/saffron/backend/exports/docx --start-id 20179 --end-id 20186 --set 1 --language odia
```

**Example F: Process Odia Set 2 using Task ID range filtering**
Extract and compile all exported Odia files belonging to the second set (IDs 20227 to 20234) as Set 2:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py /root/saffron/backend/exports /root/saffron/backend/exports/docx --start-id 20227 --end-id 20234 --set 2 --language odia
```

This compiles files following the naming convention:
`Language_Persona_Set{n}.docx` (e.g. `Telugu_Warm_Encourager_Set1.docx` or `Odia_Calm_Explainer_Set2.docx`).

---

## 4. Optional: Audit DOCX Files
If you want to scan generated Word files for any surviving raw LaTeX strings that were not cleaned up during conversion:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py --audit /root/saffron/backend/exports/docx/
```

---

## 5. One-Command Export + DOCX + Drive Upload (export_upload_docs.py)

Automates steps 2-3 plus Google Drive upload for a given language and version:

```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/export_upload_docs.py --language telugu --version 5
```

- Finds all matching conversation-editable tests in the DB, exports **accepted, comment-free** annotations (`--include-all` for rejected/unrated, `--any-comments` to include commented ones), builds persona DOCX sets with max 30 conversations each, and uploads them to the Drive folder under `<Language>/<Persona>/`.
- Set numbering continues from the last uploaded set per (language, persona), taken as max of the state CSV (`backend/upload_sets_state.csv`) and a live listing of the Drive folder. Existing Drive files are never overwritten.
- Versions: `--version 5`, `--version new` (New Version), `--version base` (no suffix).
- Useful flags: `--dry-run` (plan only), `--no-upload` (generate DOCX only), `--personas storyteller,relatable_peer`, `--chunk-size 30`, `--create-missing-folders`.
- Outputs land in `backend/exports/auto_docs/<lang>_<version>_<timestamp>/{jsonl,docx}/`.
- Drive upload needs a Google service account key at `backend/config/gdrive_service_account.json` (or `--sa-file` / `GDRIVE_SA_FILE`); share the Drive folder with the service account email as Editor. Without it, run `--no-upload`.
