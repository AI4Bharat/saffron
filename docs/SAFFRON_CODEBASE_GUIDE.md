# Saffron Codebase & Tech Stack Guide (Expanded)

This document provides a comprehensive technical walkthrough of the **Saffron** project architecture, detailing the technology stack, database schemas, REST API endpoints, user authentication, Prolific integration, data merge operations, the implementation details of the new `conversation-editable` task type, and the step-by-step execution flow across both backend and frontend.

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
│   ├── conversations_editable_tasks/ # Folder containing editable dialogue JSONL files
│   ├── main.py               # Flask application entry point
│   ├── load_config.py        # Generic script to populate DB from config files
│   ├── load_jsonl.py         # Script to load and align translation correction tasks
│   ├── load_conversation_tasks.py # Script to batch-load dialogue evaluation tasks
│   ├── load_conversation_editable_tasks.py # Script to batch-load editable dialogue tasks
│   ├── export_jsonl.py       # Exporter for translation and sentence correction tasks
│   ├── export_conversations.py # Exporter for dialogue evaluation / editable tasks
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
    │   │   └── ConversationEvaluation.vue   # UI for Accept/Reject & Editable tasks
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

The Saffron database relies on six main relational models:

1. **`Rater`**: Stores details of human annotators.
   - `id` (Integer, Primary Key): Unique auto-increment identifier.
   - `name` (String, Required): Unique username.
   - `email` (String, Required): Unique email address (or Prolific PID).
   - `password` (String, Required): Plaintext password (supports hashing).
   - `assigned_tasks` (String): Comma-separated list of Test IDs explicitly assigned to the rater.

2. **`Test`**: Represents task campaigns.
   - `id` (Integer, Primary Key): Unique identifier.
   - `test_type` (String, Required): Type of task, determining UI loading (e.g. `conversation-evaluation`, `conversation-editable`, `translation-correction`).
   - `description` (Text): Metadata descriptions describing language, persona, grade.
   - `json_entry` (JSON, Required): Array of JSON task blocks loaded from config JSONL files.

3. **`Study`**: Links tests to prolific user studies.
   - `id` (Integer, Primary Key): Unique identifier.
   - `study_id` (String, Required): External Prolific Study ID.
   - `test_id` (Integer, FK): References `Test.id`.
   - `completion_url` (String, Required): URL for redirecting completed Prolific participants.

4. **`Session`**: Tracks active Prolific user sessions.
   - `id` (Integer, Primary Key): Session sequence ID.
   - `session_id` (String, Required): Unique Prolific Session ID.
   - `study_id` (Integer, FK): References `Study.id`.
   - `prolific_pid` (String, Required): Prolific Participant ID.

5. **`Rating`**: Stores annotation responses.
   - `id` (Integer, Primary Key): Unique identifier.
   - `rater_id` (Integer, FK): References `Rater.id`.
   - `test_id` (Integer, FK): References `Test.id`.
   - `results_json` (JSON, Required): User inputs, selections, text corrections.
   - `time_of_submission` (DateTime): UTC timestamp of submission.
   - `time_taken_to_submit` (Float): Seconds taken to submit this item.
   - `page_no_progress` (String): The task item ID from the config (e.g. `"edit-test-task-1"`).
   - `completion_status` (String): Status code (e.g. `'completed'`, `'skipped'`, `'saved'`).

6. **`Consent`**: Tracks consent logs.
   - `id` (Integer, Primary Key): Consent sequence ID.
   - `rater_id` (Integer, FK): References `Rater.id`.
   - `test_id` (Integer, FK): References `Test.id`.
   - `time_of_submission` (DateTime): UTC timestamp of consent signature.

---

## 4. REST API Endpoint Specifications

The following endpoints are defined in [views.py](file:///root/saffron/backend/application/views.py):

### Authentication & Signup
- **`POST /api/login`**:
  - Request Body: `{"username": "<name>", "password": "<pass>"}`
  - Responses: `200 OK` with `{"token": "<jwt>"}` on success; `401 Unauthorized` on mismatch.
- **`POST /api/signup`**:
  - Request Body: `{"name": "<name>", "age": <int>, "gender": "<gender>", "email": "<email>", "password": "<password>"}`
  - Responses: `201 Created` with JWT token on success; `400 Bad Request` if email or username already exists.

### Task Service & Verification
- **`GET /api/test/<test_id>`**:
  - Headers: `Authorization: Bearer <token>`
  - Function: Verifies that the task isn't locked by another annotator. Returns metadata, the current page index, and the sequence of task items from `json_entry` merged with any existing `Rating` corrections or completion states.
- **`GET /api/verify_test/<test_id>`**:
  - Headers: `Authorization: Bearer <token>`
  - Responses: `200 OK` if all tasks in the test are rated as `completed` or `skipped`; `404 Not Found` if there are incomplete items remaining.

### Rating Submission
- **`POST /api/ratings`**:
  - Headers: `Authorization: Bearer <token>`
  - Request Body: `{"test_id": <int>, "results_json": {...}, "time_taken_to_submit": <ms>, "pageNo_progress": "<item_id>", "completion_status": "<status>"}`
  - Function: Creates or updates a task rating record.

### Prolific Integration
- **`GET /api/prolific/study`**:
  - Query Params: `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID`
  - Function: Logs in/registers a Prolific rater automatically. Fetches the linked test and serves items in a deterministically shuffled order unique to the participant's seed. Returns a response including JWT, consent status, and remaining session time.
- **`GET /api/prolific/consent/<test_id>`**:
  - Headers: `Authorization: Bearer <token>`
  - Function: Creates a new `Consent` log record for the rater and test.

---

## 5. Rater Response Merging Logic

When a rater opens a test via `/api/test/<test_id>` or `/api/prolific/study`, the backend dynamically merges existing database ratings into the original config structure:

1. All matching `Rating` records for `(rater_id, test_id)` are fetched.
2. The server loops through the original JSON array (`json_entry`).
3. For each original item, it checks if a corresponding `Rating` exists:
   - If yes:
     - Sets `'completion_status'` to the rating's status (`'completed'`, `'skipped'`, or `'saved'`).
     - Merges `results_json['pre_scene']` and `results_json['post_scene']` if they were corrected.
     - Loops through dialogue/conversation turns: copies updated properties (like corrected text) from `results_json` into the original turns structure, skipping source fields like `'speaker'`, `'role'`, and `'english'`.
   - If no:
     - Sets `'completion_status'` to `'uncompleted'`.
4. This ensures that when a rater resumes a session, their edits, evaluations, and comments are visible.

---

## 6. The `conversation-editable` Task Type Implementation

The `conversation-editable` task combines dialogue quality evaluation with transcription/translation correction capability.

### Loader Pipeline
- [load_conversation_editable_tasks.py](file:///root/saffron/backend/load_conversation_editable_tasks.py):
  1. Searches the `backend/conversation_editable_tasks` folder for JSONL files.
  2. Parses filenames (e.g. `conversations_marathi_calm_explainer_secondary.jsonl`) to automatically extract persona and grade constraints.
  3. Writes the batch to the `Test` database table, explicitly setting `test_type = 'conversation-editable'`.

### UI Composition
- **Routing**: In [TestView.vue](file:///root/saffron/frontend/src/views/TestView.vue) and [DynamicTestView.vue](file:///root/saffron/frontend/src/views/DynamicTestView.vue), `conversation-editable` routes load [ConversationEvaluation.vue](file:///root/saffron/frontend/src/components/ConversationEvaluation.vue), passing the `testType` prop.
- **Form Bindings**: Inside `ConversationEvaluation.vue`, if `testType === 'conversation-editable'`:
  - `isEditable` evaluates to `true`.
  - The pre-scene and post-scene elements bind to editable `sceneState` textareas.
  - The dialogue turns loop binds to a reactive `conversationState` ref, rendering a `<textarea v-model="turn.text">` block for each turn.
  - Raters can make edits directly, evaluate the overall dialogue (Accept/Reject), provide reason comments, and submit.
  - State edits are packaged and posted under `results_json`.

### Clean Exporters
- **`export_conversation_ratings`** in [export_conversations.py](file:///root/saffron/backend/export_conversations.py):
  1. Queries ratings for a given `test_id`.
  2. For each original item, retrieves `results_json` containing `"evaluation"`, `"comments"`, corrected `"pre_scene"`, `"post_scene"`, and dialogue turns.
  3. Merges all corrected scenes and dialogue turn text edits back into a deep-copied output item.
  4. Automatically cleans up temporary frontend helper keys (like `english`, `text_en`, `pre_scene_en`) from the turns and scenes.
  5. Outputs clean JSON lines back into the JSONL file.
- **`export_ratings_to_jsonl`** in [export_jsonl.py](file:///root/saffron/backend/export_jsonl.py):
  - Preserves evaluation metrics (`"evaluation"`, `"comments"`) in exported lines if they were supplied, making sure no rating metadata is discarded during other task exports.
- **`export_all_results.py`** (Bulk Exporter):
  - Maps `conversation-editable` type tests to run the updated dialogue exporter.

---

## 7. Step-by-Step Code Flow: Backend & Frontend

This section traces the execution path from the moment an annotator begins a task to the final JSONL results file export.

### Flow A: Registered User Authentication
1. **Frontend Request**: Rater inputs username/password on the login page. The browser triggers `POST /api/login`.
2. **Backend Authenticates**: The Flask backend captures the parameters in `views.py:login()` and matches them against the database `Rater` table. On match, it encodes username details into a JWT token using `generate_token(username)` with a 24-hour expiration.
3. **Frontend Token Storage**: The frontend captures the JSON response, stores the token as `'authToken'` in `localStorage`, and redirects the route to the task listing panel.

### Flow B: Prolific Anonymous User Onboarding
1. **Initial Access**: The Prolific platform redirects participants to the saffron frontend with query parameters, e.g. `/?PROLIFIC_PID=P123&STUDY_ID=S456&SESSION_ID=SE789`.
2. **Dynamic Route Load**: The Vue Router maps these arguments and loads `DynamicTestView.vue`.
3. **Fetch Config**: During the `onMounted` lifecycle hook, the component dispatches a `GET` request to `GET /api/prolific/study?PROLIFIC_PID=P123&STUDY_ID=S456&SESSION_ID=SE789`.
4. **Backend Auto-Registration**:
   - `views.py:get_test_for_prolific_user()` checks if a `Rater` with `email=PROLIFIC_PID` exists. If not, it creates a new row with a hashed random password.
   - It fetches the linked study record, checks the session status, and reads the linked test data.
   - Merges existing ratings (see **Flow C** below).
   - Randomizes the list of remaining unrated tasks using a deterministic seed `f"saffron_{rater_id}_{test_id}"`. This guarantees the rater experiences a stable, shuffled page order across refreshes.
   - Returns a response payload consisting of the test sequence, JWT token, and prolific redirection details.
5. **Consent Interceptor**: The browser intercepts the response, saves the token to local storage, and prompts the user with `ConsentForm.vue` before displaying the tasks.

### Flow C: Task Loading and Rating Merging
1. **Routing to Task**: The rater selects a task. The frontend requests `GET /api/test/<test_id>` (or uses the already fetched data from the Prolific endpoint).
2. **Database Querying**: The backend queries the `Test` record by ID, fetching the array of task dicts stored under `Test.json_entry`. It also queries the `Rating` table for all ratings belonging to the current `(rater_id, test_id)`.
3. **Merging Loop**:
   - Flask loops through each dict inside the `json_entry` list.
   - It references the task item ID (`entry['id']`).
   - If an existing rating is found, the server sets `completion_status = rating.completion_status` and merges any corrected text (like pre_scene, post_scene, and dialogue modifications) from `results_json` into the task object.
   - If no rating is found, it initializes the status as `'uncompleted'`.
4. **Component Initialization**: The frontend receives the list. It determines the active component using `<component :is="currentTestComponent">` matching on `test_type`.
5. **Component setupState**:
   - The active component (e.g. `ConversationEvaluation.vue`) runs `setupState()`, storing initial fields in reactive variables (`sceneState`, `conversationState`).
   - If `testType === 'conversation-editable'`, fields bind to textareas, giving the annotator the ability to edit.

### Flow D: Annotation Saving & Submission
1. **User Interaction**: The rater updates dialogue turns or scene narrative inputs. They make the Accept/Reject evaluation choice and enter reasoning comments.
2. **Constructing Payload**: Clicking "Save Draft" or "Submit & Next" starts the submission flow. The component constructs the payload:
   - Calculates the elapsed time on page (`Date.now() - startTime`).
   - Runs `buildResultsJson()` to construct a clean JSON state.
3. **Sending POST**: The component dispatches a `POST` request to `/api/ratings`.
4. **Backend Transaction**:
   - `views.py:create_rating()` checks that the test isn't locked by another annotator.
   - It checks the database to see if a rating already exists for the key combination `(rater_id, test_id, page_no_progress)`.
   - **Update Case**: If a record exists, it updates the `results_json`, `time_taken_to_submit`, and sets the completion status to `'completed'`, `'skipped'`, or `'saved'`.
   - **Insert Case**: If no record exists, it inserts a new `Rating` row.
   - The transaction commits, returning success to the client.
5. **UI Transition**: The frontend catches the success signal, updates the sidebar status color (Green for Done, Yellow for Saved, etc.), and shifts the active index to the next task.

### Flow E: Campaign Exporting
1. **Command Line Initiation**: The administrator initiates the export: `python export_all_results.py`.
2. **Script Execution**:
   - The script pulls all `Test` records.
   - Depending on the `test_type`, it selects the corresponding exporter script (`export_conversations.py` or `export_jsonl.py`).
3. **Export Filtering and Processing**:
   - The exporter script fetches the original configuration items list from `Test.json_entry`.
   - It queries the `Rating` table, grabbing all ratings marked as `completed` or `skipped`.
   - It groups ratings in memory by task ID (`page_no_progress`), keeping the latest record based on `time_of_submission`.
   - For each original configuration item, it matches the latest annotation and overwrites corrected scenes, corrected dialogue turns, evaluations, and comments.
   - It sanitizes the output dictionary, dropping temporary helper keys (such as `english` context lines).
4. **File Output**: The script encodes the sanitized dict array to standard JSON lines (one JSON per line) and saves the export file to `/root/saffron/backend/exports/`.
