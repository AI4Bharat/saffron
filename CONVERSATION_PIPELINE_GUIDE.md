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

### Command Format
To generate DOCX reports for a single JSONL file:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py <path_to_jsonl> <output_docx_dir>
```

### Bulk Generate Command
To generate DOCX documents for all JSONL files inside the `exports/` folder:
```bash
for f in /root/saffron/backend/exports/*.jsonl; do
  /root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py "$f" /root/saffron/backend/exports/docx
done
```

This compiles files to `/root/saffron/backend/exports/docx/` following the naming convention:
`<language>_<grade_bucket(s)>_<persona>.docx` (e.g. `hindi_elementary_calm_explainer.docx` or `hindi_secondary_reflective_mentor.docx`).

---

## 4. Optional: Audit DOCX Files
If you want to scan generated Word files for any surviving raw LaTeX strings that were not cleaned up during conversion:
```bash
/root/saffron/backend/venv/bin/python /root/saffron/backend/generate_docs.py --audit /root/saffron/backend/exports/docx/
```
