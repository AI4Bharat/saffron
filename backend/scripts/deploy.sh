#!/usr/bin/env bash
# Deploy Saffron without stalling the annotators using it.
#
#   bash scripts/deploy.sh                # detect what changed and do the least disruptive thing
#   bash scripts/deploy.sh --frontend     # rebuild + swap the Vue bundle only
#   bash scripts/deploy.sh --backend      # graceful gunicorn reload only
#   bash scripts/deploy.sh --full         # stop/start the backend (ONLY for gunicorn config changes)
#   bash scripts/deploy.sh --check        # report what would happen, change nothing
#
# WHY THIS EXISTS, three things that bite if you deploy by hand:
#
#   1. Editing a .py file on a live server is not inert. gunicorn runs without
#      --preload, so each worker imports the app itself, and --max-requests
#      recycles workers continuously. A recycled worker picks up whatever is on
#      disk at that moment, so between saving a file and reloading you have a
#      MIXED FLEET serving two versions of the code. The HUP below closes that
#      window deliberately instead of leaving it to chance.
#
#   2. `npm run build` empties dist/ before writing it (vite's emptyOutDir
#      default). For a couple of seconds the assets are gone and a fresh page
#      load 404s. We build to a staging directory and rename it into place, so
#      the swap is a directory rename rather than a rebuild-in-place.
#
#   3. A python process that imports main runs the migration suite. On
#      PostgreSQL those ALTER TABLEs take ACCESS EXCLUSIVE locks, and with
#      lock_timeout=0 a blocked one queues every other query behind it -- this
#      took the platform down for 11 minutes on 2026-08-13. Nothing here
#      imports main; the one-per-restart migration stays in start_saffron.sh.
set -uo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$BACKEND_DIR/.." && pwd)"
FRONTEND_DIR="$ROOT/frontend"
DIST="$FRONTEND_DIR/dist"
STAGE="$FRONTEND_DIR/.dist.staging"
PREV="$FRONTEND_DIR/.dist.prev"
MARKER="$ROOT/.last_deploy"
HEALTH_URL="http://127.0.0.1:4020/api/"

say()  { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
info() { printf '    %s\n' "$*"; }
warn() { printf '\033[33m    %s\033[0m\n' "$*"; }
fail() { printf '\033[31m[-] %s\033[0m\n' "$*"; exit 1; }

# ---------------------------------------------------------------- what changed

newer_than_marker() {   # newer_than_marker <dir> <find-args...>
    local dir="$1"; shift
    [ -d "$dir" ] || return 1
    if [ -f "$MARKER" ]; then
        [ -n "$(find "$dir" "$@" -newer "$MARKER" -print -quit 2>/dev/null)" ]
    else
        return 0    # never deployed: treat everything as changed
    fi
}

FRONTEND_CHANGED=false
BACKEND_CHANGED=false
CONFIG_CHANGED=false

newer_than_marker "$FRONTEND_DIR/src" -type f && FRONTEND_CHANGED=true
[ -f "$FRONTEND_DIR/package.json" ] && [ -f "$MARKER" ] &&
    [ "$FRONTEND_DIR/package.json" -nt "$MARKER" ] && FRONTEND_CHANGED=true

newer_than_marker "$BACKEND_DIR" -name '*.py' -not -path '*/venv/*' \
    -not -path '*/__pycache__/*' && BACKEND_CHANGED=true

for f in "$BACKEND_DIR/scripts/start_saffron.sh" "$BACKEND_DIR/.env"; do
    [ -f "$f" ] && [ -f "$MARKER" ] && [ "$f" -nt "$MARKER" ] && CONFIG_CHANGED=true
done

MODE="auto"
case "${1:-}" in
    --frontend) MODE=frontend ;;
    --backend)  MODE=backend ;;
    --full)     MODE=full ;;
    --check)    MODE=check ;;
    "")         ;;
    *)          fail "unknown option: $1" ;;
esac

case "$MODE" in
    frontend) FRONTEND_CHANGED=true; BACKEND_CHANGED=false; CONFIG_CHANGED=false ;;
    backend)  FRONTEND_CHANGED=false; BACKEND_CHANGED=true; CONFIG_CHANGED=false ;;
    full)     CONFIG_CHANGED=true ;;
esac

say "plan"
info "frontend changed : $FRONTEND_CHANGED"
info "backend  changed : $BACKEND_CHANGED"
info "config   changed : $CONFIG_CHANGED  (a full restart, brief downtime)"
if [ "$MODE" = check ]; then
    info "--check: nothing done."
    exit 0
fi
if ! $FRONTEND_CHANGED && ! $BACKEND_CHANGED && ! $CONFIG_CHANGED; then
    info "nothing to deploy."
    exit 0
fi

# ------------------------------------------------------------------ pre-flight

health() {  # health <attempts>
    local n="${1:-1}" code
    for _ in $(seq 1 "$n"); do
        code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$HEALTH_URL" 2>/dev/null)"
        [ "$code" = "200" ] && return 0
        sleep 1
    done
    return 1
}

if $BACKEND_CHANGED || $CONFIG_CHANGED; then
    say "pre-flight: compiling backend"
    # A syntax error only shows up when a worker boots, and by then the fleet is
    # already down. Catch it here, before anything is reloaded.
    if ! (cd "$BACKEND_DIR" && venv/bin/python -m compileall -q \
            -x '(venv|__pycache__|node_modules)' . >/tmp/deploy_compile.log 2>&1); then
        cat /tmp/deploy_compile.log
        fail "backend does not compile -- nothing was reloaded, the site is untouched."
    fi
    info "all modules compile"
fi

say "pre-flight: current health"
health 3 && info "backend is up before we start" || warn "backend is ALREADY unhealthy before deploying"

# -------------------------------------------------------------------- frontend

if $FRONTEND_CHANGED; then
    say "frontend: building to a staging directory"
    rm -rf "$STAGE" "$PREV"
    if ! (cd "$FRONTEND_DIR" && npx vite build --outDir "$STAGE" --emptyOutDir 2>&1 | tail -8); then
        rm -rf "$STAGE"
        fail "vite build failed -- dist/ untouched, the site is still serving the old bundle."
    fi
    [ -f "$STAGE/index.html" ] || { rm -rf "$STAGE"; fail "build produced no index.html"; }

    # Every asset index.html references must exist, or we would swap in a bundle
    # that 404s for anyone loading the page.
    missing=0
    while read -r asset; do
        [ -f "$STAGE/$asset" ] || { warn "missing asset: $asset"; missing=$((missing + 1)); }
    done < <(grep -oE '(src|href)="/[^"]+"' "$STAGE/index.html" | sed 's/.*"\/\(.*\)"/\1/')
    [ "$missing" -eq 0 ] || { rm -rf "$STAGE"; fail "$missing referenced asset(s) missing from the build"; }
    info "build verified ($(find "$STAGE" -type f | wc -l) files)"

    say "frontend: swapping into place"
    # Two renames, so the window where dist/ does not exist is sub-millisecond
    # rather than the ~3s a rebuild-in-place leaves it empty.
    if [ -d "$DIST" ]; then mv "$DIST" "$PREV" || fail "could not move dist aside"; fi
    if ! mv "$STAGE" "$DIST"; then
        [ -d "$PREV" ] && mv "$PREV" "$DIST"
        fail "swap failed -- previous bundle restored"
    fi
    info "dist/ updated (previous kept at $(basename "$PREV"))"
fi

# --------------------------------------------------------------------- backend

master_pid() {
    pgrep -f 'gunicorn.*main:app' 2>/dev/null | while read -r p; do
        pp="$(ps -o ppid= -p "$p" 2>/dev/null | tr -d ' ')"
        # a master's parent is not itself a gunicorn process
        ps -o args= -p "$pp" 2>/dev/null | grep -q 'gunicorn.*main:app' || echo "$p"
    done | head -1
}

rollback_frontend() {
    if [ -d "$PREV" ]; then
        warn "rolling the frontend back"
        rm -rf "$DIST"; mv "$PREV" "$DIST"
        info "previous bundle restored"
    fi
}

if $CONFIG_CHANGED; then
    say "backend: full restart (gunicorn config or .env changed)"
    warn "this drops in-flight requests for a few seconds"
    bash "$BACKEND_DIR/scripts/restart_saffron.sh" || { rollback_frontend; fail "restart failed"; }
elif $BACKEND_CHANGED; then
    MASTER="$(master_pid)"
    [ -n "$MASTER" ] || { rollback_frontend; fail "no gunicorn master found -- is the backend running?"; }
    say "backend: graceful reload (HUP $MASTER)"
    # HUP retires each worker once it has finished the request in its hands and
    # starts a replacement that imports the new code. No request is dropped, and
    # migrations do not re-run (the master keeps SAFFRON_SKIP_BOOT_MIGRATIONS=1).
    kill -HUP "$MASTER" || { rollback_frontend; fail "could not signal the master"; }
    info "waiting for the new workers"
    sleep 5
fi

# ----------------------------------------------------------------- verify

say "verifying"
if ! health 30; then
    warn "backend did not return 200 within 30s"
    rollback_frontend
    fail "DEPLOY FAILED -- check: tail -50 $BACKEND_DIR/logs/gunicorn.log"
fi
info "backend healthy"

if $FRONTEND_CHANGED; then
    code="$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 https://tts-saffron.ai4bharat.org/ 2>/dev/null)"
    if [ "$code" = "200" ]; then info "site serving (HTTP $code)"; else warn "site returned HTTP $code"; fi
fi

touch "$MARKER"
say "done"
info "deployed at $(date '+%Y-%m-%d %H:%M:%S')"
$FRONTEND_CHANGED && info "previous bundle kept at $PREV (delete when happy)"
exit 0
