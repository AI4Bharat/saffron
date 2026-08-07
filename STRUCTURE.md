# Saffron - repository layout

One app, several teams. TTS uses admin-assigned batches (the "classic"
workflow); ASR uses a pull-based pool. Adding a team means adding a Team row,
not a new codebase: every dashboard lives at /<team>/admin (component picked by
the team's workflow) and every pool workspace at /pool/<team>.

    saffron/
      backend/                 Flask API (gunicorn :4020 behind Caddy)
        main.py                app factory + engine options + one-shot migrations
        admin_reports.py       report builders imported by the app
        audio_set_labels.py    audio-seg labelling helper imported by the app
        .env                   secrets: DB URIs, admin passwords (never committed)
        application/
          models.py            Team, TeamMember, AdminUser, PoolUpload, PoolTask,
                               PoolTaskAssignment, PoolPull, PoolItem,
                               Rater, Test, Rating, Message
          migrations.py        additive, dialect-aware schema migrations + seeds
          views.py             auth, health, TTS batches/ratings, TTS dashboard
          team_api.py          teams, memberships, admin accounts
          pool_api.py          pool: pull / submit, dashboard, activity, exports
          pool_tasks.py        pool task layer: assignment, submissions, workspace
          pool_common.py       shared pool vocabulary, task types, stale-claim sweep
        loaders/               load_*.py - one loader per task type
        exporters/             export_*.py, backup/restore, docx + excel tools
        tools/                 maintenance and pipeline utilities
        scripts/
          start_saffron.sh     THE entrypoint: migrate once, run gunicorn in
                               tmux 'saffron' (single window, workers = nproc)
          migrate_sqlite_to_postgres.py   full data copy, verified row counts
        tasks/                 source data (tts/, asr/pool_source/)
        audio_segmentation/    audio clips served by /api/audio/<path>
        instance/              database.db - retired SQLite file, KEPT as the
                               documented rollback; orphans_archive.jsonl
        state/  logs/  exports/
      frontend/                Vue 3 SPA - 'npx vite build' into dist/ (Caddy
                               serves dist/ directly; a build IS a deploy)
        src/session.js         identity + active workspace + api() wrapper
        src/router/index.js    generic team routes (see Routes)
        src/views/             HomeView + TestView            (classic annotator)
                               AsrWorkspace + AsrTaskView     (pool annotator)
                               TrackingPageView               (classic dashboard)
                               AsrDashboard                   (pool dashboard)
                               TeamDashboardView              (dispatch by workflow)
                               AdminLoginView, WorkspaceView, OrgOverview
      docs/                    project documentation
      _archive/                superseded .bak copies and scratch files

## Database

PostgreSQL (credentials in backend/.env; password URL-encoded inside
DATABASE_URI). Migrated from SQLite on 2026-08-07 with ids preserved and row
counts verified; the SQLite file stays in instance/ as the rollback. Schema
changes run ONCE per deploy via the start script - workers boot with
SAFFRON_SKIP_BOOT_MIGRATIONS=1 because ALTER TABLE takes an ACCESS EXCLUSIVE
lock on PostgreSQL and a recycling worker re-running migrations would stall
every request behind that lock.

Concurrency guarantees (both engines): one task belongs to at most one
annotator (partial unique index uq_pool_task_active_assignee), and a pull
claims rows atomically (single UPDATE; FOR UPDATE SKIP LOCKED on PostgreSQL).
Claimed-but-unfinished items return to the pool automatically after
POOL_STALE_CLAIM_HOURS (default 24) - annotators cannot hand pulls back.

## Routes

    /                annotator - classic workspace (assigned batches)
    /<id>            annotator - classic task page
    /pool/<team>     annotator - pool workspace (pull items, open the queue)
    /pool/<team>/task  annotator - pool task page
                       (/asr and /asr/task redirect to /pool/asr...)
    /<team>/admin    team dashboard, component picked by the team's workflow
                     (/tracking redirects to /tts/admin)
    /workspaces      workspace chooser for annotators in more than one team
    /org             organisation admin: all teams + admin accounts
    /admin/login     admin sign-in (redirects to /login)
