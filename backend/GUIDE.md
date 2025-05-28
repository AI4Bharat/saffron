# Guide: Setting Up a New Test in TTS Saffron

This guide explains how to create and load a new test into your self-hosted TTS Saffron instance.

## Prerequisites

1.  **TTS Saffron Installed:** You have successfully set up the backend and frontend of TTS Saffron as per the main `README.md`.
2.  **Audio Files Hosted:** Your audio samples for the test must be uploaded to a publicly accessible URL (e.g., AWS S3, Azure Blob Storage, Google Cloud Storage, or any web server/CDN). TTS Saffron will play these audios directly from the URLs you provide.
3.  **Backend Running (Recommended for `load_config.py`):** While you can prepare JSONs offline, having the backend running in its virtual environment allows `load_config.py` to connect to the database.

## Steps to Set Up a New Test

There are two main parts:
1.  **Creating the Test Configuration JSON file.**
2.  **Loading the Configuration into the Database using `load_config.py`.**

---

### 1. Creating the Test Configuration JSON File

TTS Saffron uses JSON files to define the structure and content of each test. You'll need to create one JSON file for each test you want to set up.

**A. Understand Test Types and Their Structures:**

First, identify which of the supported core test types you want to create. Each type has a specific expected JSON structure for its items.

*   **Supported Test Types (and their backend identifiers, used for `--test-type` argument):**
    *   HFR: `hfr`
    *   MUSHRA - Granular: `mushra-granular`
    *   HFR - Granular: `hfr-granular`
    *   Comparative Mean Opinion Score (CMOS): `cmos`
    *   MUSHRA: `mushra`

*   **Example JSON Structures:**
    You can find example JSON files demonstrating the structure for each supported test type in the `backend/config/examples/` directory of this repository. Refer to these examples closely.

    **Key fields to pay attention to:**
    *   `"id"`: A unique integer ID for each test item *within that specific JSON file* (e.g., 1, 2, 3...). This is used for ordering and tracking progress within a test.
    *   `"audio_path"` (and similar like `"reference_audio"`, `"test_audios": [...]`): **This is critical.** Replace placeholder URLs with the actual, publicly accessible URLs of your hosted audio files.
    *   `"label"` or `"class"`: Ground truth information needed for some tests (e.g., "Human", "Machine", system name).
    *   Other fields like `"description"`, `"audio_id"`, `"Sentence"`, `"attributes"`: Include these if the corresponding frontend component for the test type utilizes them. Check the component's Vue code if unsure.

**B. Create Your JSON File:**

1.  **Choose a Name:** Give your JSON file a descriptive name, e.g., `my_mushra_test_set1.json`.
2.  **Location:** You can place this file anywhere accessible from your terminal when you run `load_config.py`. For convenience, you might place it within the `backend` directory or a subdirectory (e.g., `backend/my_custom_configs/`).
3.  **Populate:** Open the file in a text editor and create an array of test items according to the structure required for your chosen test type.

    **Example Snippet for `hfr` (Classification):**
    ```json
    [
      {
        "id": 1,
        "audio_path": "https://your-cdn.com/audio/sample_human_01.wav",
        "label": "Human",
        "description": "Speaker A, neutral tone"
      },
      {
        "id": 2,
        "audio_path": "https://your-cdn.com/audio/sample_machine_01.wav",
        "label": "Machine",
        "description": "TTS System X, sample Y"
      }
      // ... more items
    ]
    ```

4.  **Validate:** Ensure your JSON is syntactically correct. You can use an online JSON validator or a linting tool in your code editor.

---

### 2. Loading the Configuration into the Database

Once your JSON configuration file is ready, you need to load it into the TTS Saffron database. This makes the test available in the application. This is done using the `backend/load_config.py` script.

**A. Understand `load_config.py` Script:**

The `backend/load_config.py` script uses command-line arguments to specify the JSON file and its type.

*   **`config_path` (Positional Argument):** The path to your JSON configuration file.
*   **`--test-type` (Required Argument):** The type of test you are loading. This must match one of the backend identifiers listed above (e.g., `hfr`, `mushra-granular`).
*   **`--prolific` (Optional Flag):** If included, the script will attempt to create a basic `Study` entry in the database for Prolific integration. This entry will use a placeholder Prolific Study ID (`123456`) and completion URL. You will likely need to update these manually in the database later for a real Prolific study.

**B. Run the Script:**

1.  **Activate Backend Virtual Environment:**
    Ensure your backend virtual environment is activated:
    ```bash
    cd path/to/your/tts-saffron/backend
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

2.  **Verify `.env` Configuration:**
    Make sure your `backend/.env` file is configured correctly, especially the `DATABASE_URI`, so the script can connect to your PostgreSQL database.

3.  **Execute the Script:**
    Navigate to the `backend` directory in your terminal (if not already there).
    Run the script using `python load_config.py` followed by the necessary arguments.

    **Example Command:**
    To load a MUSHRA test from a file named `my_mushra_test_set1.json` located in `backend/my_custom_configs/`, and *not* create a Prolific study entry automatically:
    ```bash
    python load_config.py my_custom_configs/my_mushra_test_set1.json --test-type "mushra"
    ```

    To load a Classification (`hfr`) test from `backend/data/hfr_pilot.json` and *also* create a placeholder Prolific study entry:
    ```bash
    python load_config.py data/hfr_pilot.json --test-type "hfr" --prolific
    ```

    To load a MUSHRA Granular test:
    ```bash
    python load_config.py path/to/your/mushra_granular_config.json --test-type "mushra-granular"
    ```

4.  **Check Output:**
    The script will output messages indicating success or failure. If successful, it will print the **Test ID** for the loaded test. **Make a note of this Test ID.**
    It will also print a description of the test that was created.

**Verification:**
*   Check the script output for any error messages.
*   You can connect to your PostgreSQL database and query the `test` table to see the newly added entry. The `json_entry` column will contain the content of your JSON file, and the `test_type` column will reflect what you provided.
*   If you used the `--prolific` flag, check the `study` table as well for the placeholder entry.

---

### Using the Test

*   **For Standard Users (Logged-in):**
    Logged-in users can typically access the test by navigating to `YOUR_FRONTEND_URL/<Test_ID>` (replace `<Test_ID>` with the ID you noted from the script's output).

*   **For Prolific Users:**
    1.  **If you used `--prolific` during loading:** A basic study entry was created with a placeholder Prolific Study ID (`123456`) and a generic completion URL. You **must** update this entry in the `study` table in your PostgreSQL database with your *actual* Prolific Study ID and the *correct* Prolific completion URL for your study.
    2.  **If you did NOT use `--prolific` or need more control:** You must manually insert a row into the `study` table in your PostgreSQL database. This row should contain:
        *   `study_id`: Your actual Prolific Study ID (e.g., from the Prolific platform).
        *   `test_id`: The Test ID generated by `load_config.py`.
        *   `completion_url`: Your Prolific study completion URL (e.g., `https://app.prolific.com/submissions/complete?cc=YOUR_CODE`).
        *   You can use a tool like `psql`, pgAdmin, or DBeaver to execute an `INSERT` SQL command. Example:
            ```sql
            INSERT INTO study (id, study_id, test_id, completion_url) VALUES
            ((SELECT COALESCE(MAX(id), 0) + 1 FROM study), 'YOUR_ACTUAL_PROLIFIC_STUDY_ID', YOUR_SAFFRON_TEST_ID, 'YOUR_PROLIFIC_COMPLETION_URL');
            ```
            (Replace placeholders accordingly. Note: The `id` column in the `study` table should ideally be auto-incrementing by the database itself, so manually calculating `MAX(id)+1` is a workaround if the table wasn't set up with `SERIAL` or `IDENTITY` for its PK properly. See general project recommendations about primary keys.)

    3.  **Provide URL to Prolific Participants:**
        The URL you give to Prolific participants will be:
        `http(s)://YOUR_FRONTEND_DOMAIN/test?PROLIFIC_PID={%PROLIFIC_PID%}&STUDY_ID=YOUR_PROLIFIC_STUDY_ID&SESSION_ID={%SESSION_ID%}`
        (Replace `YOUR_FRONTEND_DOMAIN` with the domain where your Saffron frontend is hosted, and `YOUR_PROLIFIC_STUDY_ID` with the actual Prolific Study ID you used in the `study` table).

---

That's it! Your new test should now be set up and accessible. Remember to test thoroughly.
