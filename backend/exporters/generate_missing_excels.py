#!/usr/bin/env python3
"""generate_missing_excels.py — build a recording Excel for EVERY conversation DOCX on Drive that does not have one yet, in a single run."""

import argparse
import csv
import os
import re
import subprocess
import sys
import time

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BACKEND_DIR)

from docx import Document
from docx_to_excel import build_workbook, parse_doc

DOCS_DRIVE_URL = "https://drive.google.com/drive/folders/15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk"
EXCEL_DRIVE_URL = "https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"
STAGE_DIR = os.path.join(BACKEND_DIR, "exports", "pending_excels")
TMP_DOCX = os.path.join(BACKEND_DIR, "exports", "_docx_cache")
NAME_RE = re.compile(r"([A-Za-z]+)_(.+)_Set(\d+)$", re.IGNORECASE)


def parse_name(base):
    stem = os.path.splitext(base.replace("Copy of ", "").strip())[0]
    m = NAME_RE.match(stem)
    return (m.group(1).lower(), m.group(2).lower().replace(" ", "_"), int(m.group(3))) if m else None


def listing(url, what):
    import gdown
    print(f"[*] Listing the {what} Drive folder ...", flush=True)
    files = gdown.download_folder(url=url, skip_download=True, quiet=True, use_cookies=False)
    if not files:
        raise SystemExit(f"[-] Could not list the {what} folder.")
    print(f"[+] {len(files)} entr(ies)", flush=True)
    return files


def download(file_id, out_path):
    """curl by file id — far more robust than per-file gdown for a bulk run (gdown scrapes a page per file and starts returning 'too many accesses')."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    for attempt in range(3):
        try:
            subprocess.run(["curl", "-L", "-s", "-f", "--connect-timeout", "20",
                            url, "-o", out_path], check=True)
            if os.path.exists(out_path) and os.path.getsize(out_path) > 5000:
                return True
        except subprocess.CalledProcessError:
            pass
        time.sleep(1 + attempt * 2)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="stop after N files (smoke test)")
    ap.add_argument("--language", help="only this language")
    args = ap.parse_args()

    docs_files = listing(DOCS_DRIVE_URL, "conversation-DOCX")
    excel_files = listing(EXCEL_DRIVE_URL, "recording-Excel")

    have = set()
    for f in excel_files:
        base = os.path.basename(f.path)
        if base.lower().endswith(".xlsx") and not base.startswith("~$"):
            info = parse_name(base)
            if info:
                have.add(info)

    todo = []
    for f in docs_files:
        base = os.path.basename(f.path)
        if not base.lower().endswith(".docx") or base.startswith("~$"):
            continue
        info = parse_name(base)
        if not info or info in have:
            continue
        if args.language and info[0] != args.language.lower():
            continue
        todo.append((info, f))
    todo.sort(key=lambda x: x[0])

    print(f"\n[!] {len(todo)} DOCX set(s) have no Excel yet.\n")
    if args.limit:
        todo = todo[:args.limit]
        print(f"[i] --limit {args.limit}: doing {len(todo)}.\n")

    os.makedirs(STAGE_DIR, exist_ok=True)
    os.makedirs(TMP_DOCX, exist_ok=True)

    made, skipped, failed = [], 0, []
    for i, ((lang, persona, setno), f) in enumerate(todo, 1):
        lang_title = lang.title()
        persona_title = "_".join(w.title() for w in persona.split("_"))
        out_name = f"{lang_title}_{persona_title}_Set{setno}.xlsx"
        dest_dir = os.path.join(STAGE_DIR, lang_title)
        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, out_name)

        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            skipped += 1
            continue

        docx_path = os.path.join(TMP_DOCX, os.path.basename(f.path))
        try:
            if not (os.path.exists(docx_path) and os.path.getsize(docx_path) > 5000):
                if not download(f.id, docx_path):
                    raise RuntimeError("download failed")
            conversations = parse_doc(Document(docx_path))
            if not conversations:
                raise RuntimeError("no conversations parsed from the docx")
            wb = build_workbook(conversations, lang_title[:2])
            wb.save(out_path)
            turns = sum(len(c["turns"]) for c in conversations)
            made.append({"filename": out_name, "language": lang, "persona": persona,
                         "set": setno, "conversations": len(conversations),
                         "turns": turns, "source_docx": f.path})
        except Exception as e:
            failed.append({"filename": out_name, "source_docx": f.path, "error": str(e)[:200]})
            print(f"  [FAIL] {out_name}: {e}", flush=True)
            continue

        if i % 25 == 0 or i == len(todo):
            print(f"  ... {i}/{len(todo)}  made={len(made)} skipped={skipped} failed={len(failed)}",
                  flush=True)

    manifest = os.path.join(STAGE_DIR, "UPLOAD_MANIFEST.csv")
    if made:
        with open(manifest, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(made[0].keys()) + ["drive_target_folder"])
            w.writeheader()
            for r in made:
                r = dict(r)
                r["drive_target_folder"] = f"{r['language'].title()}/{r['persona'].replace('_', ' ').title()}"
                w.writerow(r)

    print(f"\n{'=' * 62}")
    print(f"generated : {len(made)}")
    print(f"skipped   : {skipped} (already generated)")
    print(f"failed    : {len(failed)}")
    print(f"output    : {STAGE_DIR}")
    if made:
        print(f"manifest  : {manifest}")
    if failed:
        bad = os.path.join(STAGE_DIR, "FAILED.csv")
        with open(bad, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(failed[0].keys()))
            w.writeheader()
            w.writerows(failed)
        print(f"failures  : {bad}")
    print(f"{'=' * 62}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
