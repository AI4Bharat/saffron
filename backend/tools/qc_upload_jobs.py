#!/usr/bin/env python3
"""qc_upload_jobs.py — disk-backed job store for the admin "Upload QC Task" pane."""

import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime

# This file lives in backend/tools/ -- the backend root is one directory up.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOBS_DIR = os.path.join(BACKEND_DIR, "qc_jobs")
VENV_PY = os.path.join(BACKEND_DIR, "venv", "bin", "python")

# Keep the pane readable: jobs older than this are pruned on listing.
MAX_JOBS_KEPT = 60


def _now():
    return datetime.now().isoformat(timespec="seconds")


def _ensure_dir():
    os.makedirs(JOBS_DIR, exist_ok=True)


def job_path(job_id):
    return os.path.join(JOBS_DIR, f"{job_id}.json")


def log_path(job_id):
    return os.path.join(JOBS_DIR, f"{job_id}.log")


def _safe_id(job_id):
    """Job ids come in over HTTP — never let one escape JOBS_DIR."""
    jid = str(job_id or "").strip()
    if not jid or not all(c.isalnum() or c in "-_" for c in jid):
        return None
    return jid


def write_job(job):
    """Atomic rewrite so a concurrent reader never sees a half-written document."""
    _ensure_dir()
    tmp = job_path(job["id"]) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(job, fh, indent=1)
    os.replace(tmp, job_path(job["id"]))
    return job


def read_job(job_id):
    jid = _safe_id(job_id)
    if not jid:
        return None
    try:
        with open(job_path(jid), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def update_job(job_id, **fields):
    job = read_job(job_id)
    if not job:
        return None
    job.update(fields)
    return write_job(job)


def read_log(job_id, tail_bytes=20000):
    jid = _safe_id(job_id)
    if not jid:
        return ""
    p = log_path(jid)
    if not os.path.exists(p):
        return ""
    size = os.path.getsize(p)
    with open(p, "rb") as fh:
        if size > tail_bytes:
            fh.seek(size - tail_bytes)
            fh.readline()          # drop the partial first line
        return fh.read().decode("utf-8", "replace")


def _pid_alive(pid):
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _reconcile(job):
    """A job whose process vanished without writing a terminal status was killed (OOM, reboot, manual kill)."""
    if job.get("status") in ("queued", "running") and job.get("pid"):
        if not _pid_alive(job["pid"]):
            job["status"] = "failed"
            job["error"] = job.get("error") or "Worker process exited without reporting a result (killed?)."
            job["finished_at"] = job.get("finished_at") or _now()
            write_job(job)
            # A killed loader would otherwise hold the single load slot forever.
            if job.get("kind") == "load":
                release_load_lock()
    return job


def get_job(job_id, with_log=False, tail_bytes=20000):
    job = read_job(job_id)
    if not job:
        return None
    job = _reconcile(job)
    if with_log:
        job["log"] = read_log(job_id, tail_bytes=tail_bytes)
    return job


def list_jobs(limit=25, kind=None):
    _ensure_dir()
    out = []
    for name in os.listdir(JOBS_DIR):
        if not name.endswith(".json"):
            continue
        job = read_job(name[:-5])
        if job and (kind is None or job.get("kind") == kind):
            out.append(_reconcile(job))
    out.sort(key=lambda j: j.get("created_at") or "", reverse=True)
    _prune(out)
    return out[:limit]


def delete_job(job_id):
    """Remove one finished job and its log."""
    job = read_job(job_id)
    if not job:
        return False, "Job not found"
    if _reconcile(job).get("status") in ("queued", "running"):
        return False, "Job is still running — stop it first"
    for p in (job_path(job["id"]), log_path(job["id"])):
        try:
            os.remove(p)
        except OSError:
            pass
    return True, "deleted"


def clear_finished():
    """Drop every job that is not running. Returns how many went."""
    n = 0
    for job in list_jobs(limit=10 ** 6):
        if job.get("status") not in ("queued", "running"):
            ok, _ = delete_job(job["id"])
            n += int(ok)
    return n


def _prune(jobs_newest_first):
    for job in jobs_newest_first[MAX_JOBS_KEPT:]:
        for p in (job_path(job["id"]), log_path(job["id"])):
            try:
                os.remove(p)
            except OSError:
                pass


def active_load_job():
    """The one running/queued load job, if any."""
    for job in list_jobs(limit=MAX_JOBS_KEPT, kind="load"):
        if job.get("status") in ("queued", "running"):
            return job
    return None


LOAD_LOCK = os.path.join(JOBS_DIR, "load.lock")
# How long a lock whose holder has no job document yet may survive.
LOCK_GRACE_SECONDS = 120


def _write_lock(fd, holder):
    with os.fdopen(fd, "w") as fh:
        fh.write(f"{holder}\n{time.time()}")


def _lock_is_stale():
    """True when the current lock can be taken over."""
    try:
        with open(LOAD_LOCK, encoding="utf-8") as fh:
            parts = fh.read().split("\n")
    except OSError:
        return True
    holder = (parts[0] if parts else "").strip()
    try:
        age = time.time() - float(parts[1])
    except (IndexError, ValueError):
        age = LOCK_GRACE_SECONDS + 1

    prev = read_job(holder) if holder else None
    if prev:
        return prev.get("status") not in ("queued", "running")
    return age > LOCK_GRACE_SECONDS


def acquire_load_lock(holder):
    """Claim the single load slot atomically."""
    _ensure_dir()
    try:
        _write_lock(os.open(LOAD_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY), holder)
        return True
    except FileExistsError:
        pass
    if not _lock_is_stale():
        return False
    release_load_lock()
    try:
        _write_lock(os.open(LOAD_LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY), holder)
        return True
    except FileExistsError:
        return False        # someone else got there first


def restamp_load_lock(job_id):
    """Point an already-held lock at the real job id once spawn has produced it."""
    _ensure_dir()
    try:
        with open(LOAD_LOCK, "w", encoding="utf-8") as fh:
            fh.write(f"{job_id}\n{time.time()}")
    except OSError:
        pass


def release_load_lock():
    try:
        os.remove(LOAD_LOCK)
    except OSError:
        pass


def spawn(kind, params, worker_script):
    """Create a job document, then launch its worker fully detached."""
    _ensure_dir()
    job_id = f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    job = {
        "id": job_id,
        "kind": kind,
        "status": "queued",
        "created_at": _now(),
        "started_at": None,
        "finished_at": None,
        "params": params,
        "result": None,
        "error": None,
        "pid": None,
        "progress": "queued",
    }
    write_job(job)

    script = os.path.join(BACKEND_DIR, worker_script)
    logf = open(log_path(job_id), "ab", buffering=0)
    try:
        proc = subprocess.Popen(
            [VENV_PY, "-u", script, job_id],
            cwd=BACKEND_DIR,
            stdout=logf,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
    except Exception as e:
        update_job(job_id, status="failed", error=f"Could not start worker: {e}",
                   finished_at=_now())
        return read_job(job_id)
    finally:
        logf.close()

    return update_job(job_id, pid=proc.pid, status="running", started_at=_now(),
                      progress="starting")


# Helpers used by the worker scripts themselves
def worker_start(job_id):
    update_job(job_id, status="running", started_at=_now(), progress="starting")


def worker_progress(job_id, text):
    update_job(job_id, progress=text)
    print(f"[progress] {text}", flush=True)


def _release_if_load(job_id):
    job = read_job(job_id)
    if job and job.get("kind") == "load":
        release_load_lock()


def worker_done(job_id, result):
    update_job(job_id, status="done", result=result, finished_at=_now(),
               progress="done")
    _release_if_load(job_id)


def worker_failed(job_id, error):
    update_job(job_id, status="failed", error=str(error)[:4000],
               finished_at=_now(), progress="failed")
    _release_if_load(job_id)


if __name__ == "__main__":
    # Tiny CLI for debugging from the server shell.
    if len(sys.argv) > 1 and sys.argv[1] == "list":
        for j in list_jobs():
            print(f"{j['id']}  {j['kind']:<8} {j['status']:<8} {j.get('progress','')}")
    elif len(sys.argv) > 2 and sys.argv[1] == "show":
        print(json.dumps(get_job(sys.argv[2], with_log=True), indent=2))
    else:
        print(__doc__)
