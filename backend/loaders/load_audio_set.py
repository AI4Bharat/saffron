#!/usr/bin/env python3
"""load_audio_set.py — one-command audio segmentation set loader."""

import argparse
import os
import re
import subprocess
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_SEG_BASE_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")
VENV_PY = os.path.join(BACKEND_DIR, "venv", "bin", "python")
LOADER = os.path.join(BACKEND_DIR, "load_audio_segmentation_tasks.py")

DEFAULT_EXCEL_DRIVE_FOLDER = "https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"

def lang_prefix(language):
    """Two-letter Excel ID prefix — first two letters of the Title-cased language, EXACTLY as docx_to_excel.py generates them: english->En, telugu->Te, hindi->Hi."""
    return language.strip().title()[:2]


def next_set_name():
    nums = []
    if os.path.isdir(AUDIO_SEG_BASE_DIR):
        for d in os.listdir(AUDIO_SEG_BASE_DIR):
            m = re.fullmatch(r"set(\d+)", d.lower())
            if m and os.path.isdir(os.path.join(AUDIO_SEG_BASE_DIR, d)):
                nums.append(int(m.group(1)))
    return f"set{max(nums) + 1 if nums else 0}"


# Single-folder mode (original)
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


# Two-source mode helpers
def _list_folder(url):
    """Return gdown's list of (id, path, local_path) for a public Drive folder, without downloading."""
    import gdown

    files = gdown.download_folder(url=url, skip_download=True, quiet=True, use_cookies=False)
    if not files:
        raise SystemExit(f"[-] Could not list Drive folder (shared as 'Anyone with the link'?): {url}")
    return files


def _curl_download(file_id, output_path):
    """Direct curl download from Drive by file id (handles the large-file 'confirm' page)."""
    base = f"https://drive.google.com/uc?export=download&id={file_id}"

    def _run(u):
        subprocess.run(["curl", "-L", "-s", "-f", "--connect-timeout", "20", u, "-o", output_path],
                       check=True)

    try:
        _run(base)
        # A small response may actually be Google's HTML virus-scan/confirm page.
        if os.path.exists(output_path) and os.path.getsize(output_path) < 50000:
            with open(output_path, "rb") as fh:
                head = fh.read(50000)
            low = head.lower()
            if b"confirm=" in low:
                m = re.search(rb"confirm=([a-zA-Z0-9\-_]+)", head)
                if m:
                    _run(f"{base}&confirm={m.group(1).decode()}")
            elif b"<html" in low:
                os.remove(output_path)
                return False
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        return False


def _download_by_id(file_id, output_path):
    """curl first (robust for bulk), fall back to gdown for the odd stubborn file."""
    if _curl_download(file_id, output_path):
        return True
    try:
        import gdown

        gdown.download(id=file_id, output=output_path, quiet=True, fuzzy=True)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 0
    except Exception:
        return False


def conv_core(text):
    """Pull the `Conv_<n>_T_<m>` core out of a filename or ID, ignoring any language token (handles `Conv_10_T_1_En`, `En_Conv_10_T_1`, `Conv_10_T_1_Telugu`, etc.)."""
    if not isinstance(text, str):
        if text is None:
            return None
        text = str(text)
    m = re.search(r"Conv_\d+_T_\d+", text, re.IGNORECASE)
    return m.group(0) if m else None


def normalize_wav_stem(stem, lang_code):
    """Fallback target name when a WAV can't be matched against the Excel: `Conv_10_T_1_En` / `Conv_10_T_1` -> `<lang_code>_Conv_10_T_1`; odd names pass through."""
    stem = stem.replace("Copy of ", "").strip()
    core = conv_core(stem)
    return f"{lang_code}_{core}" if core else stem


def excel_core_index(excel_path):
    """Map `conv_core` (lowercased) -> the exact Excel ID string, from the recording Excel."""
    import pandas as pd

    df = pd.read_excel(excel_path)
    df.columns = [str(c).strip() for c in df.columns]
    id_col = "ID" if "ID" in df.columns else df.columns[0]
    index = {}
    blanks = 0
    for raw in df[id_col].dropna():          # dropna: recording Excels can have blank ID rows
        raw = str(raw).strip()
        if not raw:
            blanks += 1
            continue
        core = conv_core(raw)
        if core:
            index[core.lower()] = raw
    skipped = len(df) - len(index)
    if skipped:
        print(f"    [i] Excel: {len(index)} usable ID(s); skipped {skipped} row(s) "
              f"without a Conv_N_T_M id (blank/heading rows).")
    return index


def download_id_wavs(audio_link, dest_dir, id_subfolder, lang_code, core_index=None):
    files = _list_folder(audio_link)
    wavs = [f for f in files
            if f.path.lower().endswith(".wav") and id_subfolder.lower() in f.path.lower()]
    if not wavs:
        print(f"[!] No WAVs found under a '{id_subfolder}' subfolder; "
              f"falling back to every .wav in the folder.")
        wavs = [f for f in files if f.path.lower().endswith(".wav")]
    if not wavs:
        raise SystemExit("[-] No .wav files found in the audio folder.")

    print(f"[*] Downloading {len(wavs)} conversation-ID WAV(s) into {dest_dir} ...")
    os.makedirs(dest_dir, exist_ok=True)
    got = 0
    failed = []
    unmatched = 0
    for idx, f in enumerate(wavs, 1):
        raw_stem = os.path.splitext(os.path.basename(f.path))[0].replace("Copy of ", "").strip()
        core = conv_core(raw_stem)
        if core_index and core and core.lower() in core_index:
            stem = core_index[core.lower()]                 # exact Excel ID -> guaranteed match
        else:
            stem = normalize_wav_stem(raw_stem, lang_code)  # fallback naming
            if core_index:
                unmatched += 1
        target = os.path.join(dest_dir, stem + ".wav")
        if os.path.exists(target) and os.path.getsize(target) > 0:
            got += 1
        elif _download_by_id(f.id, target):
            got += 1
        else:
            failed.append(os.path.basename(f.path))
        if idx % 20 == 0:
            print(f"    ... {idx}/{len(wavs)}")
    print(f"[+] Downloaded/verified {got}/{len(wavs)} WAV(s).")
    if failed:
        print(f"[WARN] {len(failed)} WAV(s) failed to download: "
              f"{failed[:10]}{' ...' if len(failed) > 10 else ''}")
    if core_index and unmatched:
        print(f"[WARN] {unmatched} WAV(s) had no matching Excel ID (named by fallback "
              f"'{lang_code}_Conv_..'); check the audio folder is for this persona/set.")


def download_matching_excel(excel_link, dest_dir, language, persona, excel_set):
    files = _list_folder(excel_link)
    want = f"{language}_{persona}_set{excel_set}".lower().replace(" ", "_")
    matches = []
    for f in files:
        if not f.path.lower().endswith(".xlsx") or os.path.basename(f.path).startswith("~$"):
            continue
        base = os.path.basename(f.path).replace("Copy of ", "").strip()
        if os.path.splitext(base)[0].lower() == want:
            matches.append((f, base))
    if not matches:
        avail = sorted({os.path.basename(f.path) for f in files if f.path.lower().endswith(".xlsx")})
        raise SystemExit(f"[-] No Excel named like '{want}.xlsx' in the Excel folder.\n"
                         f"    Available: {avail}")
    f, base = matches[0]
    target = os.path.join(dest_dir, base)
    os.makedirs(dest_dir, exist_ok=True)

    # Remember the voice actor: the excel lives in "<Language>/<persona - Recorder>/".
    parts = f.path.split("/")
    if len(parts) >= 2 and " - " in parts[-2]:
        recorder = parts[-2].split(" - ")[-1].strip()
        if recorder:
            with open(os.path.join(dest_dir, "recorder.txt"), "w", encoding="utf-8") as fh:
                fh.write(recorder + "\n")
            print(f"[+] Recorder: {recorder}")
    print(f"[*] Fetching recording Excel '{base}' ...")
    if not _download_by_id(f.id, target):
        raise SystemExit(f"[-] Failed to download Excel '{base}'.")
    print(f"[+] Excel saved: {target}")
    return target


# Shared post-download steps
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
            ids = {str(v).strip() for v in df["ID"].dropna()}
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
    # single-folder mode
    p.add_argument("--link", help="[single-folder mode] one Drive folder holding WAVs + one Excel")
    # two-source mode
    p.add_argument("--audio-link", dest="audio_link",
                   help="[two-source mode] Drive folder of recordings (with an 'EXPORTED ID' subfolder)")
    p.add_argument("--excel-link", dest="excel_link", default=DEFAULT_EXCEL_DRIVE_FOLDER,
                   help="Drive folder holding the recording Excels (default: the shared Excel folder)")
    p.add_argument("--language", default="english", help="Language (default: english)")
    p.add_argument("--persona", help="[two-source mode] persona, e.g. storyteller, calm_explainer")
    p.add_argument("--excel-set", dest="excel_set",
                   help="[two-source mode] the Set<n> number of the Excel to fetch, e.g. 2")
    p.add_argument("--id-subfolder", dest="id_subfolder", default="EXPORTED ID",
                   help="[two-source mode] WAV subfolder name to pull (default: 'EXPORTED ID')")
    # shared
    p.add_argument("--set", dest="set_name", help="Local set directory name, e.g. set5 (default: next free setN)")
    p.add_argument("--skip-download", action="store_true", help="Use the existing local set directory as-is")
    p.add_argument("--no-load", action="store_true", help="Download and validate only; skip the DB load")
    args = p.parse_args()

    two_source = bool(args.audio_link)
    if not args.skip_download and not args.link and not two_source:
        p.error("give --audio-link (+ --persona --excel-set), or --link, or --skip-download")
    if two_source and (not args.persona or not args.excel_set):
        p.error("--audio-link requires --persona and --excel-set")

    set_name = (args.set_name or ("" if args.skip_download else next_set_name())).lower().strip()
    if not set_name:
        p.error("--set is required with --skip-download")
    dest_dir = os.path.join(AUDIO_SEG_BASE_DIR, set_name)

    if args.skip_download:
        if not os.path.isdir(dest_dir):
            raise SystemExit(f"Set directory not found: {dest_dir}")
        print(f"[*] Using existing directory {dest_dir}")
    elif two_source:
        if os.path.isdir(dest_dir) and os.listdir(dest_dir):
            raise SystemExit(f"Set directory {dest_dir} already exists and is not empty. "
                             "Pick another --set name, or use --skip-download to load it.")
        lang = args.language.lower().strip()
        lang_code = lang_prefix(lang)
        print(f"[*] Two-source load: language={lang} persona={args.persona} excel-set={args.excel_set} "
              f"-> local {set_name} (Excel ID prefix '{lang_code}')")
        # Excel first: its ID column is the authoritative source of WAV names.
        excel_path = download_matching_excel(args.excel_link, dest_dir, lang, args.persona, args.excel_set)
        core_index = excel_core_index(excel_path)
        download_id_wavs(args.audio_link, dest_dir, args.id_subfolder, lang_code, core_index)
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
