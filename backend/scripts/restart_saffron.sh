#!/usr/bin/env bash
# Correct way to restart the Saffron backend.
#
# DO NOT use "tmux kill-session -t saffron" on its own. Killing the session only
# sends SIGHUP to the pane, and SIGHUP to a gunicorn MASTER means "reload workers",
# not "exit". The old master survives, keeps port 4020, respawns workers with its
# OLD config, and the replacement gunicorn then fails to bind -- which takes the
# site down while looking like a successful restart. This happened on 2026-07-31.
#
# Always terminate the master by PID, wait for the port to actually free, then start.
set -uo pipefail

echo "==> stopping existing gunicorn master(s)"
MASTERS=$(pgrep -f 'gunicorn.*main:app' | while read -r p; do
    pp=$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')
    # a master's parent is not itself a gunicorn process
    if ! ps -o args= -p "$pp" 2>/dev/null | grep -q 'gunicorn.*main:app'; then echo "$p"; fi
done)
if [ -n "${MASTERS}" ]; then
    echo "    killing: ${MASTERS}"
    # shellcheck disable=SC2086
    kill -TERM ${MASTERS}
fi

echo "==> waiting for port 4020 to free"
for i in $(seq 1 30); do
    if ! ss -ltn | grep -q ':4020'; then echo "    free after ${i}s"; break; fi
    sleep 1
done
if ss -ltn | grep -q ':4020'; then
    echo "    port STILL held after 30s -- forcing"
    # shellcheck disable=SC2086
    [ -n "${MASTERS}" ] && kill -9 ${MASTERS} 2>/dev/null
    sleep 2
fi

echo "==> starting fresh gunicorn in tmux session 'saffron'"
tmux kill-session -t saffron 2>/dev/null
tmux new-session -d -s saffron     'bash /root/saffron/backend/scripts/start_saffron.sh 2>&1 | tee -a /root/saffron/backend/logs/gunicorn.log'

for i in $(seq 1 20); do
    sleep 1
    code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:4020/api/ 2>/dev/null)
    if [ "$code" = "200" ]; then
        n=$(pgrep -P "$(pgrep -f 'gunicorn.*main:app' | head -1)" | wc -l)
        echo "==> UP after ${i}s (HTTP 200, ${n} workers)"
        exit 0
    fi
done
echo "==> FAILED to come up -- check: tmux attach -t saffron"
exit 1
