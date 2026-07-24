#!/usr/bin/env bash
# Start the Saffron backend under gunicorn on 127.0.0.1:4020 (Caddy proxies /api*).
# NOTE: sync workers (not gthread). The app pushes a single global Flask app
# context at import time and relies on it for every request, so requests must run
# in the worker's main thread. Concurrency comes from multiple worker PROCESSES,
# which is safe here because SQLite is in WAL mode (concurrent readers + one
# writer) with a 30s busy_timeout. Restart after a deploy with:
#   tmux kill-session -t saffron 2>/dev/null; bash /root/saffron/backend/start_saffron.sh
set -euo pipefail
cd /root/saffron/backend
exec venv/bin/gunicorn     --workers 6 --worker-class sync     --bind 127.0.0.1:4020     --timeout 120 --graceful-timeout 30 --keep-alive 5     --access-logfile - --error-logfile -     main:app
