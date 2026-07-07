# DOCX Generation Guide for Persona Conversations

This document outlines how to use the updated `generate_docs.py` script to generate structured Microsoft Word (.docx) documents from conversation `.jsonl` files.

---

## Command Line Arguments

The script supports the following command-line parameters to customize chunking, persona filtering, and set numbering dynamically without code modifications:

| Argument | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `input_file` | Positional | `conversations_final.jsonl` | Path to the input JSONL file or directory containing the files. |
| `output_dir` | Positional | `<language>_persona_docx` | Directory where the generated DOCX files will be written. |
| `--language` / `-l` | String | *Inferred* | Target language to filter conversations (e.g. `english`, `hindi`, etc.). |
| `--chunk-size` | Integer | `None` | The maximum number of conversations per generated DOCX file. If not specified, all conversations for a persona are put into a single document. |
| `--personas` | String | `None` | Comma-separated list of personas to process. If not specified, all personas in the default system order are processed. |
| `--persona-start-sets` | String | `None` | Comma-separated mapping of starting set numbers for specific personas (e.g. `calm_explainer=7,storyteller=4`). |
| `--version` / `-v` | String | `None` | Filter input files matching a specific version string. |
| `--set` / `-s` | Integer | `1` | Fallback starting set number if a persona is not mapped in `--persona-start-sets`. |

---

## Example Usage

### English Version 5 (Custom Chunking & Starting Sets)

To generate the English DOCX files for **Strict Disciplinarian**, **Storyteller**, **Relatable Peer**, and **Calm Explainer** for Version 5, where:
- Each document contains at most **30 conversations**
- **Calm Explainer** starts from **Set 7**
- All other personas start from **Set 4**

Run the following command from the `backend/` directory:

```bash
venv/bin/python generate_docs.py conversation_editable_tasks/version_5 exports/docx \
  --language english \
  --chunk-size 30 \
  --personas calm_explainer,strict_disciplinarian,storyteller,relatable_peer \
  --persona-start-sets calm_explainer=7,strict_disciplinarian=4,storyteller=4,relatable_peer=4
```

### Standard Generation (No Chunking)

To run the generator normally for all English personas in Version 5 without any chunking (putting all conversations for each persona in a single file starting from Set 1):

```bash
venv/bin/python generate_docs.py conversation_editable_tasks/version_5 exports/docx \
  --language english \
  --set 1
```

---

## Status Report Integration

When you run `generate_docs.py`, it automatically attempts to run `update_status()` from `update_status_report.py`. This scans the generated `.docx` files in `exports/docx/` and compiles an updated status report at:
* `/root/saffron/conversation_editable_status.md`
