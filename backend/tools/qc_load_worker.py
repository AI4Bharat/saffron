#!/usr/bin/env python3
"""qc_load_worker.py <job_id> — download + load one audio-segmentation QC set."""

import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import qc_upload_jobs as jobs

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_SEG_BASE_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")
VENV_PY = os.path.join(BACKEND_DIR, "venv", "bin", "python")
LOADER = os.path.join(BACKEND_DIR, "load_audio_set.py")


def summarise_set_dir(set_dir):
    d = os.path.join(AUDIO_SEG_BASE_DIR, set_dir)
    if not os.path.isdir(d):
        return {}
    files = os.listdir(d)
    recorder = ""
    rp = os.path.join(d, "recorder.txt")
    if os.path.exists(rp):
        recorder = open(rp, encoding="utf-8").read().strip()
    return {
        "set_dir": set_dir,
        "wavs": len([f for f in files if f.endswith(".wav")]),
        "excel": next((f for f in files if f.endswith(".xlsx") and not f.startswith("~$")), ""),
        "recorder": recorder,
    }


def invalidate_dashboard_cache():
    """Drop the 60s dashboard cache so the new batch shows up immediately."""
    try:
        from main import app  # noqa: F401
        from application.views import _dashboard_cache_invalidate
        _dashboard_cache_invalidate()
        print("[+] dashboard cache invalidated")
    except Exception as e:
        print(f"[WARN] could not invalidate the dashboard cache: {e}")


def find_new_test(set_dir):
    """The Test row the loader just created for this set directory."""
    try:
        from main import app  # noqa: F401
        from application.models import Test

        for t in Test.query.filter_by(test_type="audio-segmentation").all():
            entries = t.json_entry if isinstance(t.json_entry, list) else []
            if not entries:
                continue
            first = entries[0] or {}
            same_dir = (first.get("set_dir") == set_dir
                        or str(first.get("audio_filename") or "").startswith(set_dir + "/"))
            if same_dir:
                return {"test_id": t.id, "description": t.description,
                        "num_tasks": len(entries),
                        "excel_set": first.get("excel_set", "")}
    except Exception as e:
        print(f"[i] Could not resolve the new Test row: {e}")
    return {}


def main():
    job_id = sys.argv[1]
    job = jobs.read_job(job_id)
    if not job:
        print(f"no such job: {job_id}")
        return 1
    p = job.get("params") or {}
    jobs.worker_start(job_id)

    try:
        audio_link = (p.get("audio_link") or "").strip()
        persona = (p.get("persona") or "").strip()
        excel_set = str(p.get("excel_set") or "").strip()
        language = (p.get("language") or "english").strip().lower()
        set_dir = (p.get("set_name") or "").strip().lower()
        id_subfolder = p.get("id_subfolder") or "EXPORTED ID"
        no_load = bool(p.get("no_load"))

        if not audio_link or not persona or not excel_set:
            raise RuntimeError("audio_link, persona and excel_set are all required.")

        cmd = [VENV_PY, "-u", LOADER,
               "--audio-link", audio_link,
               "--persona", persona,
               "--excel-set", excel_set,
               "--language", language,
               "--id-subfolder", id_subfolder]
        if set_dir:
            cmd += ["--set", set_dir]
        if no_load:
            cmd.append("--no-load")

        print("[*] " + " ".join(f'"{c}"' if " " in c else c for c in cmd))
        jobs.worker_progress(job_id, f"Fetching {language} / {persona} / Set{excel_set} from Drive…")

        proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, bufsize=1)
        chosen_set = set_dir
        for line in proc.stdout:
            sys.stdout.write(line)
            sys.stdout.flush()
            s = line.strip()
            # Mirror the loader's own milestones into the job document so the pane shows something meaningful without the admin opening the log.
            m = re.search(r"-> local (set\d+)", s)
            if m:
                chosen_set = m.group(1)
            if s.startswith("[*] Downloading") or s.startswith("[*] Fetching"):
                jobs.worker_progress(job_id, s.lstrip("[*] ").strip())
            elif s.startswith("    ... "):
                jobs.worker_progress(job_id, "Downloading WAVs " + s.strip().lstrip(". "))
            elif s.startswith("[+] Downloaded/verified"):
                jobs.worker_progress(job_id, s.lstrip("[+] ").strip())
            elif s.startswith("[*] Loading set"):
                jobs.worker_progress(job_id, "Loading tasks into the database…")
            elif "Validation of" in s:
                jobs.worker_progress(job_id, "Validating the downloaded set…")

        rc = proc.wait()
        if rc != 0:
            raise RuntimeError(f"load_audio_set.py exited with code {rc}. See the log for details.")

        # NB: no relabel_all() call here — load_audio_segmentation_tasks.py already runs it (with its own db/Test handles) at the end of a successful load.

        result = {"set_dir": chosen_set, "language": language, "persona": persona,
                  "excel_set": excel_set, "no_load": no_load}
        result.update(summarise_set_dir(chosen_set) if chosen_set else {})
        if not no_load and chosen_set:
            result.update(find_new_test(chosen_set))
            # Otherwise the 60s dashboard cache hides the new batch — the same rule every admin mutation follows.
            invalidate_dashboard_cache()

        jobs.worker_done(job_id, result)
        print("[+] job complete")
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs.worker_failed(job_id, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
