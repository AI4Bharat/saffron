# NCERT Batch Task Loading & Exporting Instructions

This guide lists the exact commands to split and upload the NCERT task datasets from `/data/dashboard` into batches of 250 items, check database task associations, and export the annotated tasks.

---

## 1. Running the Servers & Troubleshooting Maintenance Status

If the frontend displays a *"backend server is currently unreachable"* alert, make sure your backend server is active on port `4020`.

### Start the Backend
1. Open a terminal and run:
   ```bash
   cd backend
   source venv/bin/activate
   python main.py
   ```
   *Note: Keep this terminal window open.*

---

## 2. Uploading all NCERT Language Tasks

Each language JSONL file in `/data/dashboard` contains approximately 750 tasks. We split them into batches of **250 tasks each** using the `split_and_load.py` script. The original English source is passed as `--english` to align teacher/student dialogue turns.

Ensure your virtual environment is active in the `backend` directory, then run the commands below.

### NCERT Upload Commands (Split to 250 tasks per ID)

```bash
# 1. Bengali
python split_and_load.py /data/dashboard/conversations_ncert_bengali.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Bengali Translation" --batch-size 250

# 2. Gujarati
python split_and_load.py /data/dashboard/conversations_ncert_gujarati.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Gujarati Translation" --batch-size 250

# 3. Hindi
python split_and_load.py /data/dashboard/conversations_ncert_hindi.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Hindi Translation" --batch-size 250

# 4. Kannada
python split_and_load.py /data/dashboard/conversations_ncert_kannada.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Kannada Translation" --batch-size 250

# 5. Malayalam
python split_and_load.py /data/dashboard/conversations_ncert_malayalam.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Malayalam Translation" --batch-size 250

# 6. Marathi
python split_and_load.py /data/dashboard/conversations_ncert_marathi.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Marathi Translation" --batch-size 250

# 7. Odia
python split_and_load.py /data/dashboard/conversations_ncert_odia.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Odia Translation" --batch-size 250

# 8. Tamil
python split_and_load.py /data/dashboard/conversations_ncert_tamil.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Tamil Translation" --batch-size 250

# 9. Telugu
python split_and_load.py /data/dashboard/conversations_ncert_telugu.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Telugu Translation" --batch-size 250

# 10. Urdu
python split_and_load.py /data/dashboard/conversations_ncert_urdu.jsonl --english /data/dashboard/conversations_ncert.jsonl --description-prefix "NCERT Urdu Translation" --batch-size 250
```

---

## 3. Summarizing DB Tasks and Languages

To see which **Test ID** in the database corresponds to which language and batch portion, run the database summary script inside the active `backend` environment:

```bash
python summarize_db.py
```

### Example Summary Output
```text
===============================================================================================
Test ID    | Description                                             | Language     | Total Tasks 
===============================================================================================
11         | Hindi Gravity Pilot - Part 1 (Tasks 1 to 1)             | Hindi        | 1           
12         | NCERT Bengali Translation - Part 1 (Tasks 1 to 250)     | Bengali      | 250         
13         | NCERT Bengali Translation - Part 2 (Tasks 251 to 500)   | Bengali      | 250         
14         | NCERT Bengali Translation - Part 3 (Tasks 501 to 750)   | Bengali      | 250         
15         | NCERT Gujarati Translation - Part 1 (Tasks 1 to 250)    | Gujarati     | 250         
...
===============================================================================================
```

---

## 4. Exporting the Annotated Tasks

To export the final cleaned JSONL translations for any batch portion, run `export_jsonl.py` with its **Test ID** (which you can look up using the summary script above):

```bash
python export_jsonl.py [TEST_ID] [OUTPUT_PATH]
```

#### Examples:
```bash
# Export Bengali Part 1 corrections
python export_jsonl.py 12 ncert_bengali_part1_corrected.jsonl

# Export Hindi Part 3 corrections
python export_jsonl.py 20 ncert_hindi_part3_corrected.jsonl
```
The output file will contain the original keys and metadata with updated, corrected translation texts.
