#!/usr/bin/env python3
"""
sync_all_state.py — one command to sync every pipeline state CSV.

  1. Docx set numbers   upload_sets_state.csv   <- live Drive docs folder
  2. Excel set numbers  excel_sets_state.csv    <- live Drive excel folder
  3. Audio-seg manifest audio_segmentation_state.csv  <- the annotation DB + local set dirs

Notes:
  * Run this AFTER you have uploaded the docs/excels to Drive — --sync-state makes the
    CSV mirror Drive EXACTLY, so anything generated-but-not-yet-uploaded would be dropped.
  * version_state.csv is intentionally NOT synced: versions are not encoded on Drive,
    so that CSV is the source of truth and is maintained automatically by export_upload_docs.py.
  * Audio segmentation has no Drive folder, so its "sync" rebuilds a manifest of the loaded
    audio-segmentation Tests straight from the DB (id, language, persona, set, task/wav counts).

Usage:  venv/bin/python sync_all_state.py
"""

import csv
import datetime
import os
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
VENV_PY = os.path.join(BACKEND_DIR, "venv", "bin", "python")
AUDIO_SEG_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")
AUDIO_CSV = os.path.join(BACKEND_DIR, "audio_segmentation_state.csv")


def run_sync(script, title):
    print("=" * 72)
    print(title)
    print("=" * 72)
    rc = subprocess.call([VENV_PY, os.path.join(BACKEND_DIR, script), "--sync-state"],
                         cwd=BACKEND_DIR)
    print(f"[{'OK' if rc == 0 else 'FAILED rc=' + str(rc)}] {title}\n")
    return rc == 0


def sync_audio_manifest():
    print("=" * 72)
    print("Audio-segmentation manifest  (rebuilt from the DB + local set dirs)")
    print("=" * 72)
    sys.path.append(BACKEND_DIR)
    from main import app
    from application.models import Test

    rows = []
    with app.app_context():
        tests = Test.query.filter_by(test_type="audio-segmentation").order_by(Test.id).all()
        for t in tests:
            parts = [p.strip() for p in (t.description or "").split(" - ")]
            language = parts[1] if len(parts) > 1 else ""
            persona = parts[2] if len(parts) > 2 else ""
            set_name = parts[3] if len(parts) > 3 else ""
            entries = t.json_entry if isinstance(t.json_entry, list) else []
            n_tasks = len(entries)
            set_dir = ""
            if entries:
                af = str(entries[0].get("audio_filename", ""))
                set_dir = af.split("/")[0] if "/" in af else ""
            wav_count = 0
            if set_dir:
                d = os.path.join(AUDIO_SEG_DIR, set_dir)
                if os.path.isdir(d):
                    wav_count = len([f for f in os.listdir(d) if f.lower().endswith(".wav")])
            rows.append((t.id, language, persona, set_name, set_dir, n_tasks, wav_count))

    now = datetime.datetime.now().isoformat(timespec="seconds")
    tmp = AUDIO_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["test_id", "language", "persona", "set", "set_dir",
                    "num_tasks", "wav_files", "updated_at"])
        for r in rows:
            w.writerow(list(r) + [now])
    os.replace(tmp, AUDIO_CSV)

    print(f"Wrote {len(rows)} audio-segmentation Test(s) -> {AUDIO_CSV}")
    for tid, language, persona, set_name, set_dir, n_tasks, wav_count in rows:
        print(f"  Test {tid}: {language} / {persona} / {set_name} "
              f"({n_tasks} tasks, {wav_count} wav in {set_dir or '?'})")
    print()
    return True


def main():
    ok1 = run_sync("export_upload_docs.py", "Docx set numbers  (upload_sets_state.csv)  <- Drive")
    ok2 = run_sync("docx_to_excel.py", "Excel set numbers  (excel_sets_state.csv)  <- Drive")
    ok3 = sync_audio_manifest()

    print("=" * 72)
    print(f"SUMMARY: docx {'OK' if ok1 else 'FAILED'} | excel {'OK' if ok2 else 'FAILED'} | "
          f"audio {'OK' if ok3 else 'FAILED'}")
    print("(version_state.csv left untouched — versions aren't on Drive.)")
    print("=" * 72)
    sys.exit(0 if (ok1 and ok2 and ok3) else 1)


if __name__ == "__main__":
    main()
