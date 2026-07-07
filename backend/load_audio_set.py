#!/usr/bin/env python3
"""
load_audio_set.py — one-command audio segmentation set loader.

Given a Google Drive link (folder of WAVs + one Excel), this script:
  1. Downloads everything into /root/saffron/backend/audio_segmentation/<set>/
  2. Strips any "Copy of " prefixes Drive adds to filenames.
  3. Validates the set: exactly one .xlsx, WAV files matched against the Excel ID column.
  4. Loads the tasks into the DB via the existing load_audio_segmentation_tasks.py.

Usage:
    venv/bin/python load_audio_set.py --link "https://drive.google.com/drive/folders/XXXX"
    venv/bin/python load_audio_set.py --link "..." --set set5      # explicit set name
    venv/bin/python load_audio_set.py --link "..." --no-load       # download + validate only
    venv/bin/python load_audio_set.py --set set3 --skip-download   # (re)validate + load existing dir

If --set is omitted a new setN directory (highest existing N + 1) is created.
"""

import argparse
import os
import re
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_SEG_BASE_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")
VENV_PY = os.path.join(BACKEND_DIR, "venv", "bin", "python")
LOADER = os.path.join(BACKEND_DIR, "load_audio_segmentation_tasks.py")


def next_set_name():
    nums = []
    if os.path.isdir(AUDIO_SEG_BASE_DIR):
        for d in os.listdir(AUDIO_SEG_BASE_DIR):
            m = re.fullmatch(r"set(\d+)", d.lower())
            if m and os.path.isdir(os.path.join(AUDIO_SEG_BASE_DIR, d)):
                nums.append(int(m.group(1)))
    return f"set{max(nums) + 1 if nums else 0}"


def download(link, dest_dir):
    import gdown

    os.makedirs(dest_dir, exist_ok=True)
    print(f"[*] Downloading from Drive into {dest_dir} ...")
    if "folders" in link:
        out = gdown.download_folder(url=link, output=dest_dir, quiet=False, use_cookies=False)
        if not out:
            raise SystemExit("[-] Folder download failed. Is the link shared as "
                             "'Anyone with the link'?")
    else:
        out = gdown.download(url=link, output=dest_dir + os.sep, quiet=False, fuzzy=True)
        if not out:
            raise SystemExit("[-] File download failed.")
    print(f"[+] Download complete.")


def strip_copy_prefixes(dest_dir):
    renamed = 0
    for root, _, files in os.walk(dest_dir):
        for name in files:
            if name.startswith("Copy of "):
                new_name = name.replace("Copy of ", "", 1)
                src, dst = os.path.join(root, name), os.path.join(root, new_name)
                if os.path.exists(dst):
                    print(f"[WARN] Both '{name}' and '{new_name}' exist; leaving '{name}' as is.")
                    continue
                os.rename(src, dst)
                renamed += 1
    if renamed:
        print(f"[+] Renamed {renamed} 'Copy of ...' file(s).")


def flatten_single_subfolder(dest_dir):
    """gdown sometimes nests the folder's contents one level deep; flatten that."""
    entries = os.listdir(dest_dir)
    if len(entries) == 1 and os.path.isdir(os.path.join(dest_dir, entries[0])):
        inner = os.path.join(dest_dir, entries[0])
        for name in os.listdir(inner):
            os.rename(os.path.join(inner, name), os.path.join(dest_dir, name))
        os.rmdir(inner)
        print(f"[+] Flattened nested folder '{entries[0]}'.")


def validate(dest_dir):
    files = os.listdir(dest_dir)
    xlsx = [f for f in files if f.endswith(".xlsx") and not f.startswith("~$")]
    wavs = sorted(f for f in files if f.endswith(".wav"))
    print(f"\nValidation of {dest_dir}:")
    print(f"  Excel files: {len(xlsx)}  {xlsx}")
    print(f"  WAV files:   {len(wavs)}")
    ok = True
    if len(xlsx) != 1:
        print("  [FAIL] Need exactly one .xlsx in the set directory.")
        ok = False
    if not wavs:
        print("  [FAIL] No .wav files found.")
        ok = False
    if ok:
        try:
            import pandas as pd

            df = pd.read_excel(os.path.join(dest_dir, xlsx[0]))
            df.columns = [str(c).strip() for c in df.columns]
            if "ID" not in df.columns:
                df.rename(columns={df.columns[0]: "ID"}, inplace=True)
            ids = set(df["ID"].astype(str).str.strip())
            wav_ids = {os.path.splitext(w)[0] for w in wavs}
            unmatched = sorted(wav_ids - ids)
            print(f"  Excel rows: {len(ids)}; WAVs matching an Excel ID: {len(wav_ids & ids)}")
            if unmatched:
                print(f"  [WARN] {len(unmatched)} WAV(s) have no Excel row and will be "
                      f"skipped by the loader: {unmatched[:10]}{' ...' if len(unmatched) > 10 else ''}")
        except Exception as e:
            print(f"  [WARN] Could not cross-check Excel IDs: {e}")
    return ok


def main():
    p = argparse.ArgumentParser(description="Download an audio segmentation set from Drive and load it into the DB.")
    p.add_argument("--link", help="Google Drive folder (or file) link, shared as 'Anyone with the link'")
    p.add_argument("--set", dest="set_name", help="Set directory name, e.g. set5 (default: next free setN)")
    p.add_argument("--skip-download", action="store_true", help="Use the existing set directory as-is")
    p.add_argument("--no-load", action="store_true", help="Download and validate only; skip the DB load")
    args = p.parse_args()

    if not args.skip_download and not args.link:
        p.error("--link is required (or pass --skip-download to use an existing directory)")

    set_name = (args.set_name or ("" if args.skip_download else next_set_name())).lower().strip()
    if not set_name:
        p.error("--set is required with --skip-download")
    dest_dir = os.path.join(AUDIO_SEG_BASE_DIR, set_name)

    if args.skip_download:
        if not os.path.isdir(dest_dir):
            raise SystemExit(f"Set directory not found: {dest_dir}")
        print(f"[*] Using existing directory {dest_dir}")
    else:
        if os.path.isdir(dest_dir) and os.listdir(dest_dir):
            raise SystemExit(f"Set directory {dest_dir} already exists and is not empty. "
                             "Pick another --set name, or use --skip-download to load it.")
        download(args.link, dest_dir)
        flatten_single_subfolder(dest_dir)

    strip_copy_prefixes(dest_dir)
    if not validate(dest_dir):
        raise SystemExit("\nValidation failed; DB load not attempted.")

    if args.no_load:
        print(f"\n--no-load: set '{set_name}' is downloaded and valid. Load it later with:\n"
              f"  {VENV_PY} {LOADER} {set_name}")
        return

    print(f"\n[*] Loading set '{set_name}' into the database...")
    rc = subprocess.call([VENV_PY, LOADER, set_name])
    sys.exit(rc)


if __name__ == "__main__":
    main()
