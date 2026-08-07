# Getting Started with TTS Saffron (Self-Hosting Guide)

This guide will walk you through setting up TTS Saffron on your own server. For a general overview of the project, please refer to the main [README.md](./README.md).

## Table of Contents
- [Prerequisites](#prerequisites)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Audio File Hosting](#audio-file-hosting)
- [Creating and Loading Test Configurations](#creating-and-loading-test-configurations)
- [Setting up for Prolific Studies](#setting-up-for-prolific-studies)
- [Running in Production](#running-in-production)

## Prerequisites

### General
- Git

### Backend
- Python 3.7+
- pip (Python package installer)
- PostgreSQL server (running and accessible)

### Frontend
- Node.js (LTS version recommended)
- npm or yarn

## Backend Setup

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/AI4Bharat/tts-saffron
    cd tts-saffron
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    cd backend
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file in the `backend` directory and set the following variables:
        *   `SECRET_KEY`: A long, random, and strong string for Flask session security.
        *   `DATABASE_URI`: Your PostgreSQL connection string, e.g., `postgresql://your_user:your_password@your_host:your_port/your_database_name`.
        *   `JWT_SECRET_KEY`: A long, random, and strong string for JWT token signing.
        *   **Important:** Ensure your PostgreSQL database is created and the user has permissions.

5.  **Initialize the Database:**
    *   If setting up for the first time with a new database:
        ```bash
        flask db init  # Only run this once ever for a new project setup
        ```
    *   Create and apply migrations:
        ```bash
        flask db migrate -m "Initial migration"
        flask db upgrade
        ```
    *   Any time you change backend models in the future, you'll run `flask db migrate` and `flask db upgrade`.

6.  **(Development) Run the Backend Server:**
    For development, you can use the Flask development server:
    ```bash
    flask run --host=0.0.0.0 --port=4020
    ```
    For production, see the [Running in Production](#running-in-production) section.

## Frontend Setup

1.  **Navigate to Frontend Directory:**
    ```bash
    cd frontend  # From the project root
    ```

2.  **Install Dependencies:**
    ```bash
    npm install
    # or
    # yarn install
    ```

3.  **Configure Environment Variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file in the `frontend` directory:
        *   `VITE_API_BASE_URL`: Set this to the URL where your backend API is accessible (e.g., `http://localhost:4020` if running locally, or your production backend URL). The `/api` suffix is usually handled by the frontend code itself, so just the base URL is needed here.

4.  **(Development) Run the Frontend Server:**
    ```bash
    npm run dev
    # or
    # yarn dev
    ```
    This will typically start a development server on `http://localhost:5173` (or another port).

5.  **(Production) Build the Frontend:**
    ```bash
    npm run build
    ```
    This will create a `dist` folder in `frontend` containing the static assets to be served by a web server like Nginx.

## Audio File Hosting

-   All audio files referenced in your test configurations (`audio_path` fields in JSON) **must be publicly accessible via URLs**.
-   You can host these files on:
    -   Cloud storage (AWS S3, Google Cloud Storage, Azure Blob Storage) with public read access.
    -   A Content Delivery Network (CDN).
    -   Your own web server.
-   Ensure the URLs in your test configuration JSON files point correctly to these hosted audio files.

## Creating and Loading Test Configurations

Setting up new tests involves creating JSON configuration files that define your test items (audio samples, ground truth, etc.) and then loading these files into the Saffron database.

**For detailed step-by-step instructions, including JSON structure examples for each supported test type and how to use the `load_config.py` script, please refer to the dedicated guide:**

➡️ **[Guide: Setting Up a New Test in TTS Saffron](./backend/GUIDE.md)**

This guide will walk you through:
- Understanding the JSON structure for each of the 5 core test types.
- Finding example JSON files in `backend/config/examples/`.
- Modifying and running `backend/load_config.py` to load your custom tests.
- Noting the `test_id` generated, which is crucial for accessing the test or linking it to Prolific studies.

## Setting up for Prolific Studies

If you plan to use Prolific for recruiting participants:
1.  **Load Test Data:** First, load your test configuration into Saffron using `load_config.py` as described in the [Setting Up a New Test Guide](./backend/GUIDE.md). Note the `test_id` generated for the test you want to use.
2.  **Create a Study Record:** You need to manually insert a record into the `study` table in your PostgreSQL database.
    *   Connect to your PostgreSQL database using `psql` or a GUI tool (like pgAdmin, DBeaver).
    *   Execute an SQL command like:
        ```sql
        INSERT INTO study (id, study_id, test_id, completion_url) VALUES
        ((SELECT COALESCE(MAX(id), 0) + 1 FROM study), 'YOUR_PROLIFIC_STUDY_ID', YOUR_SAFFRON_TEST_ID, 'YOUR_PROLIFIC_COMPLETION_URL');
        ```
        Replace:
        *   `YOUR_PROLIFIC_STUDY_ID`: The Study ID provided by Prolific for your study.
        *   `YOUR_SAFFRON_TEST_ID`: The `test_id` you noted when loading the test configuration into Saffron.
        *   `YOUR_PROLIFIC_COMPLETION_URL`: The completion URL Prolific provides (e.g., `https://app.prolific.com/submissions/complete?cc=YOUR_CODE`).
3.  **Provide Test URL to Prolific:**
    *   The URL you give to Prolific participants will be:
        `http(s)://YOUR_FRONTEND_DOMAIN/test?PROLIFIC_PID={%PROLIFIC_PID%}&STUDY_ID=YOUR_PROLIFIC_STUDY_ID&SESSION_ID={%SESSION_ID%}`
    *   Replace `YOUR_FRONTEND_DOMAIN` with the domain where your Saffron frontend is hosted.
    *   Replace `YOUR_PROLIFIC_STUDY_ID` with the actual Prolific Study ID.
    *   Prolific will replace `{%PROLIFIC_PID%}`, `{%STUDY_ID%}`, and `{%SESSION_ID%}` with the actual values for each participant.

## Running in Production

-   **Backend:**
    -   Use a production-grade WSGI server like Gunicorn:
        ```bash
        gunicorn -w 4 -b 0.0.0.0:4020 main:app
        ```
        (Adjust `-w` workers as needed).
    -   Consider using a process manager like `systemd` or `supervisor` to manage the Gunicorn process.
-   **Frontend:**
    -   Build the frontend: `cd frontend && npm run build`.
    -   Serve the static files from `frontend/dist` using a web server like Nginx or Apache.
    -   Configure your web server to also act as a reverse proxy for backend API requests (e.g., proxying requests to `/api/*` to `http://localhost:4020`).
    -   **Example Basic Nginx Configuration Snippet:**
        ```nginx
        server {
            listen 80;
            server_name your_domain.com;

            # Serve Frontend
            location / {
                root /path/to/your/saffron/frontend/dist;
                try_files $uri $uri/ /index.html;
            }

            # Proxy Backend API
            location /api {
                proxy_pass http://localhost:4020; # Or wherever your Gunicorn is running
                proxy_set_header Host $host;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
                proxy_set_header X-Forwarded-Proto $scheme;
            }
        }
        ```
        Replace `/path/to/your/saffron/frontend/dist` and `your_domain.com`. You'll also need SSL configuration (HTTPS) for a public site.

---
Return to main [README.md](./README.md).