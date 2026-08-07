#!/usr/bin/env python3
"""audit_docx_vs_excel.py — which conversation DOCX sets have no recording Excel yet?"""

import csv
import json
import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
DOCS_FOLDER_ID = "15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk"
EXCEL_FOLDER_ID = "1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"
OUT_CSV = os.path.join(BACKEND_DIR, "docx_excel_audit.csv")
OUT_JSON = os.path.join(BACKEND_DIR, "docx_excel_audit.json")


def listing(folder_id, what):
    import gdown
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"[*] Listing {what} folder ...", flush=True)
    files = gdown.download_folder(url=url, skip_download=True, quiet=True, use_cookies=False)
    if not files:
        raise SystemExit(f"[-] Could not list the {what} folder: {url}")
    print(f"[+] {len(files)} entr(ies) in the {what} folder", flush=True)
    return files


def parse(base):
    """'English_Calm_Explainer_Set12.docx' -> (english, calm_explainer, 12)."""
    stem = os.path.splitext(base.replace("Copy of ", "").strip())[0]
    m = re.match(r"([A-Za-z]+)_(.+)_Set(\d+)$", stem, re.IGNORECASE)
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower(), int(m.group(3))


def collect(files, ext):
    out = {}
    unparsed = []
    for f in files:
        base = os.path.basename(f.path)
        if not base.lower().endswith(ext) or base.startswith("~$"):
            continue
        info = parse(base)
        if not info:
            unparsed.append(f.path)
            continue
        out[info] = f.path
    return out, unparsed


def main():
    docs_files = listing(DOCS_FOLDER_ID, "conversation-DOCX")
    excel_files = listing(EXCEL_FOLDER_ID, "recording-Excel")

    docs, docs_bad = collect(docs_files, ".docx")
    excels, excel_bad = collect(excel_files, ".xlsx")

    missing = sorted(set(docs) - set(excels))
    orphan = sorted(set(excels) - set(docs))

    print()
    print("=" * 72)
    print(f"DOCX sets on Drive : {len(docs)}")
    print(f"Excel sets on Drive: {len(excels)}")
    print(f"DOCX with NO Excel : {len(missing)}   <-- to generate")
    print(f"Excel with no DOCX : {len(orphan)}")
    if docs_bad:
        print(f"unparsed docx names: {len(docs_bad)} (e.g. {docs_bad[:2]})")
    if excel_bad:
        print(f"unparsed xlsx names: {len(excel_bad)} (e.g. {excel_bad[:2]})")
    print("=" * 72)

    by_lang = {}
    for lang, persona, s in missing:
        by_lang.setdefault(lang, []).append((persona, s))
    print("\nMISSING EXCELS BY LANGUAGE")
    for lang in sorted(by_lang):
        items = by_lang[lang]
        personas = {}
        for p, s in items:
            personas.setdefault(p, []).append(s)
        print(f"\n  {lang.title()}  ({len(items)} sets)")
        for p in sorted(personas):
            nums = sorted(personas[p])
            rng = f"{nums[0]}-{nums[-1]}" if len(nums) > 1 else str(nums[0])
            print(f"      {p:<24} {len(nums):>3} sets   (Set {rng})")

    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["language", "persona", "set", "docx_path", "has_excel"])
        for key in sorted(set(docs) | set(excels)):
            lang, persona, s = key
            w.writerow([lang, persona, s, docs.get(key, ""), "yes" if key in excels else "no"])

    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"missing": [list(k) for k in missing],
                   "docs_total": len(docs), "excels_total": len(excels),
                   "orphan": [list(k) for k in orphan]}, fh, indent=1)

    print(f"\n[+] Full table -> {OUT_CSV}")
    print(f"[+] Machine-readable -> {OUT_JSON}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
