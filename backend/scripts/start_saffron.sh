#!/usr/bin/env bash
# Saffron backend runner -- ONE tmux session, ONE window, gunicorn only.
#
# Usage:
#   bash scripts/start_saffron.sh          # (re)start the backend inside tmux session 'saffron'
#   bash scripts/start_saffron.sh run      # run gunicorn in the foreground (this is what tmux runs)
#
# WORKERS: sync worker processes, not gthread (the app pushes a global Flask app
# context at import time, so requests must run in the worker's main thread;
# concurrency comes from processes, which is safe because SQLite runs in WAL
# mode -- concurrent readers + one writer -- with a 30s busy_timeout).
# Defaults to every core; override with SAFFRON_WORKERS=<n>.
#
# MEMORY: a freshly booted worker holds ~370 MB and can grow to ~1.35 GB after a
# heavy dashboard/export request (glibc keeps freed arenas). --max-requests
# recycles each worker after ~400 requests (jittered so they do not all restart
# together), so grown workers are reclaimed and the fleet stays inside RAM. A
# cold import takes ~0.4s and the restart is graceful, so no request is dropped.
set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SESSION=saffron
WORKERS="${SAFFRON_WORKERS:-$(nproc)}"
LOG="$BACKEND_DIR/logs/gunicorn.log"

if [[ "${1:-}" == "run" ]]; then
    cd "$BACKEND_DIR"
    # Apply schema migrations exactly ONCE per (re)start. Workers then boot with
    # SAFFRON_SKIP_BOOT_MIGRATIONS=1: on PostgreSQL the boot-time ALTER TABLEs
    # take ACCESS EXCLUSIVE locks, and recycling workers re-running them would
    # repeatedly stall every request behind that lock queue.
    venv/bin/python3 -c "import main" >> "$LOG" 2>&1
    export SAFFRON_SKIP_BOOT_MIGRATIONS=1
    exec venv/bin/gunicorn \
        --workers "$WORKERS" --worker-class sync \
        --bind 127.0.0.1:4020 \
        --timeout 120 --graceful-timeout 30 --keep-alive 5 \
        --max-requests 400 --max-requests-jitter 80 \
        --access-logfile "$LOG" --error-logfile "$LOG" \
        --capture-output \
        main:app
fi

mkdir -p "$BACKEND_DIR/logs"
tmux kill-session -t "$SESSION" 2>/dev/null || true

# A previous master can outlive its tmux session (it reparents to init). Stop it gracefully and wait for the port, or the new master cannot bind and gives up.
pkill -TERM -f 'gunicorn.*127.0.0.1:4020' 2>/dev/null || true
for _ in $(seq 1 30); do
    ss -tln 2>/dev/null | grep -q '127.0.0.1:4020' || break
    sleep 1
done

tmux new-session -d -s "$SESSION" -n backend \
    "bash '$BACKEND_DIR/scripts/start_saffron.sh' run"
echo "Saffron backend starting in tmux session '$SESSION' ($WORKERS workers)."
echo "  watch:   tmux attach -t $SESSION"
echo "  logs:    tail -f $LOG"
