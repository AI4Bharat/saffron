#!/usr/bin/env python3
"""backfill_audio_set_labels.py — one-off/idempotent fixer for audio-segmentation labels."""
import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BACKEND_DIR)

from main import app
from application.database import db
from application.models import Test
import audio_set_labels as L

EXCEL_DRIVE = "https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"


def recorder_map():
    """{excel basename lower -> recorder name} from the Excel Drive folder layout."""
    import gdown

    out = {}
    files = gdown.download_folder(url=EXCEL_DRIVE, skip_download=True, quiet=True)
    for f in files or []:
        if not f.path.lower().endswith(".xlsx"):
            continue
        parts = f.path.split("/")
        if len(parts) < 2:
            continue
        folder = parts[-2]                     # e.g. "Story Teller - Soniya"
        rec = folder.split(" - ")[-1].strip() if " - " in folder else ""
        base = os.path.basename(f.path).replace("Copy of ", "").strip().lower()
        if rec:
            out[base] = rec
    return out


def main():
    apply = "--apply" in sys.argv
    print("MODE:", "APPLY" if apply else "DRY RUN (pass --apply to write)")

    print("\nReading recorder names from the Excel Drive folder...")
    rmap = recorder_map()
    for k, v in sorted(rmap.items()):
        print(f"  {k:<42} -> {v}")

    print("\nrecorder.txt per set dir:")
    for set_dir in sorted(os.listdir(L.AUDIO_DIR)):
        d = os.path.join(L.AUDIO_DIR, set_dir)
        if not os.path.isdir(d):
            continue
        xl = [f for f in os.listdir(d) if f.endswith(".xlsx") and not f.startswith("~$")]
        if not xl:
            print(f"  {set_dir:<6} (no excel, skipped)")
            continue
        rec = rmap.get(xl[0].replace("Copy of ", "").strip().lower())
        if not rec:
            print(f"  {set_dir:<6} {xl[0]:<38} -> recorder unknown")
            continue
        print(f"  {set_dir:<6} {xl[0]:<38} -> {rec}")
        if apply:
            with open(os.path.join(d, "recorder.txt"), "w", encoding="utf-8") as fh:
                fh.write(rec + "\n")

    print("\nLabels:")
    with app.app_context():
        if apply:
            L.relabel_all(db, Test)
        else:
            # dry run: show what relabel_all WOULD produce, without committing
            tests = Test.query.filter_by(test_type="audio-segmentation").order_by(Test.id).all()
            info = []
            for t in tests:
                entries = t.json_entry if isinstance(t.json_entry, list) else []
                sd = L.set_dir_of(entries)
                lab = L.excel_set_label(sd)
                if not lab:
                    continue
                lang = (entries[0].get("language") if entries else None) or "English"
                pers = (entries[0].get("persona") if entries else None) or "Unknown"
                info.append((t, f"Audio Segmentation - {lang} - {pers} - {lab}", sd, entries))
            counts = {}
            for _t, b, _d, _e in info:
                counts[b] = counts.get(b, 0) + 1
            for t, base, sd, entries in info:
                # recorder.txt may not exist yet in dry run -> fall back to the drive map
                brk = ""
                if counts[base] > 1:
                    bits = []
                    xl = [f for f in os.listdir(os.path.join(L.AUDIO_DIR, sd))
                          if f.endswith(".xlsx") and not f.startswith("~$")]
                    rec = rmap.get(xl[0].replace("Copy of ", "").strip().lower()) if xl else None
                    if rec:
                        bits.append(rec)
                    lo, hi = L.conv_range(entries)
                    if lo is not None:
                        bits.append(f"Conv {lo}-{hi}" if lo != hi else f"Conv {lo}")
                    brk = f" ({', '.join(bits)})" if bits else ""
                new = base + brk
                mark = "" if new == t.description else "   <-- CHANGE"
                print(f"  {t.id}: {new!r}{mark}")
        if not apply:
            print("\nDry run only - nothing written.")


if __name__ == "__main__":
    main()
