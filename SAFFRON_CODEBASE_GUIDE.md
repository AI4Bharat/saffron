# Saffron Codebase & Tech Stack Guide

This document provides a detailed walkthrough of the **Saffron** project architecture, including the technology stack, database models, backend API endpoints, loading/exporting workflows, and frontend Vue 3 application structure.

---

## 1. Technology Stack

### Backend
- **Core Framework**: [Flask](https://flask.palletsprojects.com/) (Python 3)
- **Database ORM**: [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/) (SQLAlchemy-backed, supports SQLite and PostgreSQL)
- **Authentication**: JWT (JSON Web Tokens via `PyJWT`)
- **Caching**: [Flask-Caching](https://flask-caching.readthedocs.io/) (configured for filesystem caching at `/tmp/flask-cache` with a default 10-minute timeout)
- **Logging**: Rotating file handler logging to `error.log`

### Frontend
- **Framework**: [Vue 3](https://vuejs.org/) (Composition API, `<script setup>`)
- **Build Tool**: [Vite](https://vitejs.dev/)
- **Routing**: [Vue Router](https://router.vuejs.org/)
- **Styling**: [Bootstrap 5](https://getbootstrap.com/) (with customized colors, typography, gradients, glassmorphism card layouts, and subtle CSS transitions)
- **Icons**: [Bootstrap Icons](https://icons.getbootstrap.com/)

---

## 2. Directory Layout

```
saffron/
├── backend/
│   ├── application/
│   │   ├── database.py       # Initializes SQLAlchemy DB object
│   │   ├── models.py         # SQLAlchemy DB models schema definitions
│   │   └── views.py          # API route handlers & backend controllers
│   ├── config/               # Configuration settings (YAML/JSON)
│   ├── conversation_tasks/   # Folder containing dialogue evaluation JSONL files
│   ├── main.py               # Flask application entry point
│   ├── load_config.py        # Generic script to populate DB from config files
│   ├── load_jsonl.py         # Script to load and align translation correction tasks
│   ├── load_conversation_tasks.py # Script to batch-load dialogue evaluation tasks
│   ├── export_jsonl.py       # Exporter for translation and sentence correction tasks
│   ├── export_conversations.py # Exporter for dialogue evaluation tasks
│   ├── export_all_results.py # Bulk exporter script for all tests
│   └── requirements.txt      # Python backend dependencies
└── frontend/
    ├── src/
    │   ├── App.vue           # Root Vue component with Navbar
    │   ├── main.js           # Vue application entry point
    │   ├── config.js         # Stores API base URLs
    │   ├── components/       # Reusable UI pages/components
    │   │   ├── ConsentForm.vue              # Pre-test terms consent page
    │   │   ├── GroundingPage.vue            # Rater instructions/tutorial page
    │   │   ├── SentenceCorrection.vue       # UI for translation sentence tasks
    │   │   ├── TranslationCorrection.vue    # UI for full conversation edits
    │   │   └── ConversationEvaluation.vue   # UI for Accept/Reject evaluation tasks
    │   ├── router/
    │   │   └── index.js      # Vue router config (Paths: /, /login, /test/:id, etc.)
    │   └── views/
    │       ├── AdminDashboard.vue   # Admin tracking metrics dashboard
    │       ├── DynamicTestView.vue  # Prolific user routing view
    │       ├── HomeView.vue         # Rater task assignment selection list
    │       └── TestView.vue         # Logged-in rater annotation interface
    └── package.json          # Node dependencies & scripts
```

---

## 3. Database Schema (`backend/application/models.py`)

The Saffron schema consists of six relational models mapping to database tables:

1. **`Rater`**: Represents annotators.
   - `id`: Primary key (Integer).
   - `name`: Unique username (String).
   - `email`: Rater email/Prolific ID (String).
   - `password`: Password (String).
   - `assigned_tasks`: Comma-separated list of assigned Test IDs (String, e.g. `"1,2,5"`).

2. **`Test`**: Represents a loaded task batch/campaign.
   - `id`: Primary key (Integer).
   - `test_type`: Task type identifier (String, e.g. `conversation-evaluation`, `translation-correction`).
   - `description`: Batch metadata description (Text).
   - `json_entry`: List of all task items loaded from JSONL (JSON column).

3. **`Study`**: Links database tests to external user studies.
   - `id`: Primary key (Integer).
   - `study_id`: Prolific study ID (String).
   - `test_id`: Linked test identifier (Foreign key referencing `Test.id`).
   - `completion_url`: Redirection link for completed studies (String).

4. **`Session`**: Tracks active Prolific user sessions.
   - `id`: Primary key (Integer).
   - `session_id`: Prolific session ID (String).
   - `study_id`: Linked study (Foreign key referencing `Study.id`).
   - `prolific_pid`: Prolific Participant ID (String).

5. **`Rating`**: Stores annotation responses per task item.
   - `id`: Primary key (Integer).
   - `rater_id`: Rater (Foreign key referencing `Rater.id`).
   - `test_id`: Test batch (Foreign key referencing `Test.id`).
   - `results_json`: Saved answers, text modifications, and metrics (JSON column).
   - `time_of_submission`: Submission timestamp (DateTime).
   - `time_taken_to_submit`: Duration of session in seconds (Float).
   - `page_no_progress`: Identifier of the specific page/item ID within the test (String).
   - `completion_status`: Status of submission (String, e.g. `'completed'`, `'skipped'`, `'saved'`).

6. **`Consent`**: Stores the consent status of raters.
   - `id`: Primary key (Integer).
   - `rater_id`: Rater (Foreign key referencing `Rater.id`).
   - `test_id`: Test batch (Foreign key referencing `Test.id`).
   - `time_of_submission`: Timestamp of consent (DateTime).

---

## 4. Key Workflows

### Task Loading Pipeline
1. Tasks are formatted in JSONL files (one JSON object per line).
2. Command-line loading scripts are executed:
   - For Translation/Sentence tasks: `python load_jsonl.py <path_to_translated.jsonl> --english <path_to_english.jsonl>` merges English source texts and loads data as `translation-correction` or `sentence-correction` tests.
   - For Conversation Accept/Reject tasks: `python load_conversation_tasks.py` parses file names, derives persona and grade guidelines, and saves tasks as `conversation-evaluation` tests.
3. The loaded arrays of items are written to the database under `Test.json_entry`.

### Annotation & Persistence
1. When a rater starts a test, the server retrieves items from `Test.json_entry`.
2. Existing submissions from the `Rating` table are retrieved and merged on-the-fly. This allows the frontend to show previous entries, continue drafts (completion status `'saved'`), and track progress.
3. Raters modify fields or make selections, triggering `POST /api/ratings` (or `/api/prolific/rating`) to save progress back to the database.

### Data Exporting
- **CSV Export**: Admins can request a CSV summary for a specific Test ID at `GET /api/admin/export_csv/<test_id>`. The backend inspects `test_type` and outputs task-type-specific columns (original text, corrections, speaker dialogue tables, evaluations, etc.).
- **JSONL Export**: Exporter scripts query `Rating` entries, group by the latest submission per task item, deep-copy the original loaded data item from `Test.json_entry`, merge the corrections (e.g. edited translations or accept/reject evaluations), pop off temporary UI fields (like english helper keys), and write clean JSON lines to the exports folder.

---

## 5. Frontend Architecture & Routing

### views/
- **`HomeView.vue`**: Allows logged-in raters to see all tests assigned to them, showing their percentage progress and completion status.
- **`TestView.vue`**: Serves as the primary workspace for registered users. It fetches test data, renders a sidebar displaying all tasks in the current batch with color indicators (Green for Done, Orange for Skipped, Yellow for Saved, Grey for Open), and dynamically instantiates the correct annotation component based on `test_type`.
- **`DynamicTestView.vue`**: Similar to `TestView.vue`, but handles prolific anonymous participants routing without logins. It uses query parameters (`PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID`) to automatically sign up/log in the participant under an anonymous session, manages timers, shows the consent page, and redirects them to Prolific on completion.
- **`AdminDashboard.vue`**: A secure area for administrators to look at active user counts, progress per language, and individual rater metrics, and download exported CSV files.

### components/
- **`TranslationCorrection.vue`**: Enables side-by-side translation correction. Raters can look at the English context, compare it with the translated target text, and directly edit text blocks. Supports RTL languages.
- **`SentenceCorrection.vue`**: A clean, single-sentence focused layout for translation verification.
- **`ConversationEvaluation.vue`**: A dialogue-bubble interface where raters read a multi-turn conversation and rate each turn's quality before giving a final Accept/Reject vote and descriptive feedback comments.
