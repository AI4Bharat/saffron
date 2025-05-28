# TTS Saffron

## Table of Contents
- [Overview](#overview)
- [Supported Test Types](#supported-test-types)
- [Features](#features)
- [Technologies Used](#technologies-used)
- [Getting Started (Self-Hosting Guide)](#getting-started-self-hosting-guide)
- [Creating and Loading Test Configurations](#creating-and-loading-test-configurations)
- [Setting up for Prolific Studies](#setting-up-for-prolific-studies)
- [API Endpoints](#api-endpoints)
- [Frontend Components Overview](#frontend-components-overview)
- [Contributing](#contributing)

## Overview

TTS Saffron is a comprehensive platform designed to evaluate and improve text-to-speech (TTS) technologies. It allows researchers and developers to conduct various audio-based tests by leveraging user feedback, aiming to enhance the quality and naturalness of machine-generated speech. This repository provides the codebase for self-hosting the TTS Saffron platform.

The platform supports:
- **Secure User Authentication:** Users can register and log in to participate in tests.
- **Prolific Integration:** Seamlessly run studies with participants from Prolific, with automatic rater profile creation.
- **Diverse Audio-Based Tests:** Evaluate different aspects of TTS quality.

## Supported Test Types

This version of TTS Saffron is focused on the following core test types:

1.  **Human/Machine Classification (Similarity-based):**
    *   Backend Identifier: `hfr`
    *   Description: Users listen to an audio sample and classify it as either human-spoken or machine-generated.
    *   Frontend Component: `HFR.vue`
2.  **MUSHRA - Granular:**
    *   Backend Identifier: `mushra-granular`
    *   Description: A MUSHRA-style test where users rate multiple test audio samples against a reference, focusing on various degradation aspects and quality attributes.
    *   Frontend Component: `MushraGranular.vue`
3.  **Machine vs Human Granular (Single Stimulus with Ground Truth):**
    *   Backend Identifier: `hfr-granular`
    *   Description: Users listen to a single audio sample and classify it as human or machine. If machine, they provide granular reasons for their classification.
    *   Frontend Component: `HFRGranular.vue`
4.  **Comparative Mean Opinion Score (CMOS):**
    *   Backend Identifier: `cmos`
    *   Description: Users compare multiple test audio samples against a reference and provide a CMOS score indicating relative preference or quality.
    *   Frontend Component: `CMOS.vue`
5.  **MUSHRA:**
    *   Backend Identifier: `mushra`
    *   Description: The traditional MUSHRA test where users rate the overall quality of several test audio samples compared to a reference and hidden anchors.
    *   Frontend Component: `Mushra.vue`

## Features
- **User Authentication:** Secure sign-up and login functionalities with JWT-based authentication.
- **CRUD Operations:** Manage users, tests, and ratings through a robust backend.
- **Dynamic Testing:** Supports multiple core test types with real-time progress tracking.
- **Audio Playback:** Integrated audio players using WaveSurfer.js for seamless audio interaction.
- **Responsive Design:** Ensures a good user experience across devices (optimized for desktop/laptop).
- **Error Handling:** Comprehensive error logging (backend) and user-friendly error messages (frontend).
- **Prolific Integration:** Supports running tests with participants from app.prolific.com.

## Technologies Used
- **Backend:**
  - [Python](https://www.python.org/)
  - [Flask](https://flask.palletsprojects.com/)
  - [Flask_SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
  - JWT for authentication
  - [python-dotenv](https://github.com/theskumar/python-dotenv) for environment variables
  - [Flask-CORS](https://flask-cors.readthedocs.io/)
- **Frontend:**
  - [Vue.js](https://vuejs.org/)
  - [Vue Router](https://router.vuejs.org/)
  - [WaveSurfer.js](https://wavesurfer-js.org/)
  - [Bootstrap](https://getbootstrap.com/) for styling
- **Database:**
  - [PostgreSQL](https://www.postgresql.org/)

## Getting Started (Self-Hosting Guide)

For detailed instructions on how to set up TTS Saffron on your own server, including prerequisites, backend setup, frontend setup, and running in production, please refer to our comprehensive guide:

➡️ **[Getting Started with TTS Saffron (Self-Hosting Guide)](./GETTING_STARTED.md)**

## Creating and Loading Test Configurations

Setting up new tests involves creating JSON configuration files that define your test items (audio samples, ground truth, etc.) and then loading these files into the Saffron database.

**For detailed step-by-step instructions, including JSON structure examples for each supported test type and how to use the `load_config.py` script, please refer to the dedicated guide:**

➡️ **[Guide: Setting Up a New Test in TTS Saffron](./backend/GUIDE.md)**

## Setting up for Prolific Studies

If you plan to use Prolific for recruiting participants, the setup involves loading your test data into Saffron, creating a study record in the database, and providing the correct test URL to Prolific.

For detailed steps, please see the "Setting up for Prolific Studies" section in the:

➡️ **[Getting Started with TTS Saffron (Self-Hosting Guide)](./GETTING_STARTED.md#setting-up-for-prolific-studies)**

## API Endpoints
-   **Authentication:**
    -   `POST /api/signup`: Register a new user.
    -   `POST /api/login`: Authenticate a user and retrieve a JWT token.
-   **Tests (Logged-in Users):**
    -   `GET /api/test/<int:test_id>`: Retrieve test details for a logged-in user.
-   **Ratings (Logged-in Users):**
    -   `POST /api/ratings`: Submit a new rating.
    -   `PUT /api/ratings/<int:rating_id>`: Update an existing rating (less commonly used by standard flow).
-   **Prolific Integration:**
    -   `GET /api/prolific/study`: Retrieve test details for a Prolific participant (uses query params: `PROLIFIC_PID`, `STUDY_ID`, `SESSION_ID`).
    -   `POST /api/prolific/study`: (Admin) Create a new Prolific study linking to a Saffron test.
    -   `POST /api/prolific/session`: (Internal) Called when a Prolific user starts a test.
    -   `POST /api/prolific/rating`: Submit a rating from a Prolific participant.
    -   `GET /api/prolific/consent/<int:test_id>`: Record user consent for a test.
-   **(Optional Admin) Tracking & Results:**
    -   `GET /api/tracking`: View progress across tests (requires special token).
    -   `GET /api/results` or `GET /api/results/<int:test_id>`: Download all ratings or ratings for a specific test (requires special token).

## Frontend Components Overview
-   **Views (`frontend/src/views/`):**
    -   `HomeView.vue`: Page for logged-in users to enter a Test ID.
    -   `LoginView.vue` & `SignupView.vue`: User authentication.
    -   `TestView.vue`: Main container for displaying tests for logged-in users.
    -   `DynamicTestView.vue`: Main container for displaying tests for Prolific users.
    -   `CompletionView.vue`: Shown after a test is completed.
    -   `TrackingPageView.vue`: (Optional Admin) Displays test progress.
-   **Test Components (`frontend/src/components/`):**
    -   `HFR.vue`: For `hfr`.
    -   `MushraGranular.vue`: For `mushra-granular`.
    -   `HFRGranular.vue`: For `hfr-granular`.
    -   `CMOS.vue`: For `cmos`.
    -   `Mushra.vue`: For `mushra`.
-   **Shared Components (`frontend/src/components/`):**
    -   `ConsentForm.vue`: Used in the Prolific flow.
    -   `GroundingPage.vue`: (If applicable) Used for Prolific flow to familiarize users.

## Contributing
Contributions are welcome! Please follow these steps:
1.  Fork the repository.
2.  Create a new branch: `git checkout -b feature/YourFeature`
3.  Commit your changes: `git commit -m "Add YourFeature"`
4.  Push to the branch: `git push origin feature/YourFeature`
5.  Open a Pull Request.