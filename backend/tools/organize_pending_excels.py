#!/usr/bin/env python3
"""organize_pending_excels.py — put the staged Excels into <Language>/<Persona>/ folders that mirror the conversation-DOCX (recording script) folders exactly."""

import collections
import csv
import os
import re
import shutil
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
STAGE_DIR = os.path.join(BACKEND_DIR, "exports", "pending_excels")
AUDIT_CSV = os.path.join(BACKEND_DIR, "docx_excel_audit.csv")
EXCEL_DRIVE_URL = "https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"


def parse_name(base):
    stem = os.path.splitext(base.replace("Copy of ", "").strip())[0]
    m = re.match(r"([A-Za-z]+)_(.+)_Set(\d+)$", stem, re.IGNORECASE)
    return (m.group(1).lower(), m.group(2).lower().replace(" ", "_"), int(m.group(3))) if m else None


def docx_folders():
    """{(lang, persona, set): 'English/Calm Explainer'} from the audit table."""
    out = {}
    with open(AUDIT_CSV, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if not r["docx_path"]:
                continue
            key = (r["language"], r["persona"], int(r["set"]))
            out[key] = os.path.dirname(r["docx_path"])
    return out


def existing_excel_folders():
    """{(lang, persona): 'English/Story Teller - Soniya'} live from Drive."""
    import gdown
    files = gdown.download_folder(url=EXCEL_DRIVE_URL, skip_download=True,
                                  quiet=True, use_cookies=False)
    out = {}
    for f in files or []:
        base = os.path.basename(f.path)
        if not base.lower().endswith(".xlsx") or base.startswith("~$"):
            continue
        info = parse_name(base)
        if info:
            out[(info[0], info[1])] = os.path.dirname(f.path)
    return out


def main():
    if not os.path.isdir(STAGE_DIR):
        raise SystemExit(f"[-] Nothing staged at {STAGE_DIR}")

    print("[*] Reading the DOCX/Excel audit ...")
    doc_folder = docx_folders()
    print(f"[+] {len(doc_folder)} recording script(s) on Drive")

    print("[*] Listing the recording-Excel Drive folder ...")
    existing = existing_excel_folders()
    print(f"[+] {len(existing)} (language, persona) folder(s) already have Excels")

    files = []
    for root, _, names in os.walk(STAGE_DIR):
        for n in names:
            if n.endswith(".xlsx") and not n.startswith("~$"):
                files.append(os.path.join(root, n))
    print(f"[+] {len(files)} staged Excel(s) to organise\n")

    rows, unmatched = [], []
    for path in sorted(files):
        base = os.path.basename(path)
        info = parse_name(base)
        if not info or info not in doc_folder:
            unmatched.append(base)
            continue
        lang, persona, setno = info
        target_rel = doc_folder[info]                    # e.g. 'English/Calm Explainer'
        dest_dir = os.path.join(STAGE_DIR, target_rel)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, base)
        if os.path.abspath(dest) != os.path.abspath(path):
            shutil.move(path, dest)
        rows.append({
            "filename": base, "language": lang, "persona": persona, "set": setno,
            "local_folder": target_rel,
            "upload_into_existing": existing.get((lang, persona), ""),
            "source_script": os.path.join(target_rel, base.replace(".xlsx", ".docx")),
        })

    # Drop the now-empty language-only folders left behind by the move.
    for d in sorted((os.path.join(r, x) for r, dirs, _ in os.walk(STAGE_DIR) for x in dirs),
                    key=len, reverse=True):
        try:
            os.rmdir(d)
        except OSError:
            pass

    manifest = os.path.join(STAGE_DIR, "UPLOAD_MANIFEST.csv")
    with open(manifest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r["language"], r["persona"], r["set"])))

    # ---- coverage report: scripts vs excels, per language and persona ----
    scripts = collections.Counter((l, p) for (l, p, s) in doc_folder)
    ready = collections.Counter((r["language"], r["persona"]) for r in rows)
    print(f"{'LANGUAGE':<10} {'PERSONA':<24} {'SCRIPTS':>8} {'READY':>7} {'ON DRIVE':>9}")
    print("-" * 62)
    tot_s = tot_r = 0
    for lang in sorted({l for l, _ in scripts}):
        for persona in sorted({p for l, p in scripts if l == lang}):
            s = scripts[(lang, persona)]
            r = ready[(lang, persona)]
            d = s - r
            tot_s += s
            tot_r += r
            flag = "" if r + d == s else "   <-- MISMATCH"
            print(f"{lang:<10} {persona:<24} {s:>8} {r:>7} {d:>9}{flag}")
    print("-" * 62)
    print(f"{'TOTAL':<35} {tot_s:>8} {tot_r:>7} {tot_s - tot_r:>9}")

    if unmatched:
        print(f"\n[!] {len(unmatched)} staged file(s) had no matching script: {unmatched[:5]}")

    print(f"\n[+] Organised into <Language>/<Persona>/ under {STAGE_DIR}")
    print(f"[+] Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
