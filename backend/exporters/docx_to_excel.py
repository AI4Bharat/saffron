#!/usr/bin/env python3
"""docx_to_excel.py — convert conversation DOCX sets into recording Excel files."""

import argparse
import csv
import datetime
import io
import os
import re
import sys
import zipfile

from docx import Document
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# This file lives in backend/exporters/ -- the backend root is one directory up.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXCEL_DRIVE_FOLDER_ID = "1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"
EXCEL_DRIVE_URL = f"https://drive.google.com/drive/folders/{EXCEL_DRIVE_FOLDER_ID}"
# Source conversation DOCX files live here (same folder export_upload_docs.py uploads to)
DOCS_DRIVE_FOLDER_ID = "15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk"
DOCS_DRIVE_URL = f"https://drive.google.com/drive/folders/{DOCS_DRIVE_FOLDER_ID}"
STATE_CSV = os.path.join(BACKEND_DIR, "state/excel_sets_state.csv")
RUNS_DIR = os.path.join(BACKEND_DIR, "exports", "excel_runs")

DOCX_NAME_RE = re.compile(r"^([A-Za-z]+)_(.+)_Set(\d+)\.docx$", re.IGNORECASE)
XLSX_NAME_RE = re.compile(r"^(?:copy of )?([A-Za-z]+)_(.+)_Set(\d+)\.xlsx$", re.IGNORECASE)

# DOCX parsing (IDs use the two-letter language PREFIX, e.g.
_SKIP_PREFIXES = (
    "Teacher Persona",
    "Persona Description",
    "Teacher:",
    "Student:",
    "Pre-Scene",
    "Post-Scene",
    "Voice Direction",
    "\U0001F4DA",  # books emoji grade heading
    "Filtered",
    "────",
)

_TURN_RE = re.compile(r"^(.+?\s*\((?:Teacher|Student)\)):\s*(.+)$", re.DOTALL)
_CONV_RE = re.compile(r"^Conversation\s+(\d+)\s*$", re.IGNORECASE)


def _is_skip(text):
    if any(text.startswith(p) for p in _SKIP_PREFIXES):
        return True
    return " Conversations " in text and "—" in text  # doc title line


def parse_doc(doc):
    """Return a list of {num, turns:[{turn_num, speaker, dialogue}]} dicts."""
    conversations = []
    current = None
    turn_num = 0

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        m = _CONV_RE.match(text)
        if m:
            if current and current["turns"]:
                conversations.append(current)
            current = {"num": int(m.group(1)), "turns": []}
            turn_num = 0
            continue

        if current is None or _is_skip(text):
            continue

        m = _TURN_RE.match(text)
        if m:
            turn_num += 1
            current["turns"].append({
                "turn_num": turn_num,
                "speaker": m.group(1).strip(),
                "dialogue": m.group(2).strip(),
            })

    if current and current["turns"]:
        conversations.append(current)

    return conversations


# Workbook building (yellow theme)
_HEADER_FILL = PatternFill("solid", fgColor="FFD966")
_HEADER_FONT = Font(color="000000", bold=True)
_WRAP = Alignment(wrap_text=True, vertical="top")


def _style_header(ws, col_widths):
    for col_idx, width in enumerate(col_widths, start=1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def _wrap_column(ws, col, start_row=2):
    for row in ws.iter_rows(min_row=start_row, min_col=col, max_col=col):
        for cell in row:
            cell.alignment = _WRAP


def build_workbook(conversations, lang_code):
    wb = openpyxl.Workbook()

    ws1 = wb.active
    ws1.title = "Turns"
    ws1.append(["ID", "Speaker", "Dialogue"])
    ws1.row_dimensions[1].height = 18
    _style_header(ws1, [35, 22, 90])

    ws2 = wb.create_sheet("Conversations")
    ws2.append(["ID", "Conversation"])
    ws2.row_dimensions[1].height = 18
    _style_header(ws2, [25, 110])

    for conv in conversations:
        # Language code is a PREFIX: <Lg>_Conv_N / <Lg>_Conv_N_T_M
        conv_id = f"{lang_code}_Conv_{conv['num']}"
        full_lines = []
        for turn in conv["turns"]:
            turn_id = f"{lang_code}_Conv_{conv['num']}_T_{turn['turn_num']}"
            ws1.append([turn_id, turn["speaker"], turn["dialogue"]])
            full_lines.append(f"{turn['speaker']}: {turn['dialogue']}")
        ws2.append([conv_id, "\n".join(full_lines)])

    _wrap_column(ws1, 3)
    _wrap_column(ws2, 2)
    return wb


# Set-number state (CSV + live Drive listing) — same mechanism as the docs
def load_state():
    state = {}
    if os.path.exists(STATE_CSV):
        with open(STATE_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    state[(row["language"].lower(), row["persona"].lower())] = int(row["last_set"])
                except (KeyError, ValueError):
                    continue
    return state


def save_state(state):
    tmp = STATE_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["language", "persona", "last_set", "updated_at"])
        for (lang, persona), n in sorted(state.items()):
            w.writerow([lang, persona, n, datetime.datetime.now().isoformat(timespec="seconds")])
    os.replace(tmp, STATE_CSV)


def drive_last_sets():
    """Highest existing Set number per (language, persona) in the Excel Drive folder, parsed from the xlsx filenames."""
    result = {}
    try:
        import gdown

        files = gdown.download_folder(url=EXCEL_DRIVE_URL, skip_download=True, quiet=True)
        for f in files or []:
            m = XLSX_NAME_RE.match(os.path.basename(f.path))
            if not m:
                continue
            key = (m.group(1).lower(), m.group(2).lower().replace(" ", "_"))
            result[key] = max(result.get(key, 0), int(m.group(3)))
    except Exception as e:
        print(f"[WARN] Could not list the Excel Drive folder: {e}")
    return result


def sync_state_from_drive():
    drive_sets = drive_last_sets()
    if not drive_sets:
        raise SystemExit("Drive listing returned nothing; state CSV left untouched.")
    save_state(drive_sets)
    print(f"Excel state CSV rewritten from Drive -> {STATE_CSV}")
    for (lang, persona), n in sorted(drive_sets.items()):
        print(f"  {lang:<10} {persona:<22} last_set = {n}")


# Drive fetch (conversation docs folder) — anonymous, folder is link-shared
def _norm(s):
    return re.sub(r"[\s_]+", "_", s.strip().lower())


def find_docx_locally(language, persona, set_no):
    """Fallback: look for the docx in past export runs (exports/auto_docs/*/docx) and the local docx cache (exports/_docx_cache) for sets that were generated on this server but are not (or no longer) on Drive."""
    want = (_norm(language), _norm(persona), int(set_no))
    hits = []
    for rel in (("exports", "auto_docs"), ("exports", "_docx_cache")):
        for root, _, names in os.walk(os.path.join(BACKEND_DIR, *rel)):
            for n in names:
                m = DOCX_NAME_RE.match(n)
                if m and (_norm(m.group(1)), _norm(m.group(2)), int(m.group(3))) == want:
                    hits.append(os.path.join(root, n))
    return max(hits, key=os.path.getmtime) if hits else None


def _download_drive_file(file_id, out_path):
    """Fetch one Drive file by id, clearing the confirmation page if shown.

    gdown handles the small ones; anything served behind Drive's virus-scan
    interstitial comes back as HTML instead of bytes, and that form is posted
    here rather than treated as a failure.
    """
    import re as _re

    import gdown
    import requests

    tmp = out_path + ".part"
    try:
        got = gdown.download(id=file_id, output=out_path, quiet=True)
        if got and os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            return out_path
    except Exception as e:
        print(f"  gdown could not fetch it ({str(e)[:70]}); trying the "
              f"confirmation form")

    session = requests.Session()
    session.headers["User-Agent"] = "Mozilla/5.0"
    r = session.get("https://drive.google.com/uc",
                    params={"export": "download", "id": file_id},
                    stream=True, timeout=120)
    if "text/html" in (r.headers.get("Content-Type") or "").lower():
        body = r.text
        r.close()
        action = _re.search(r'action="([^"]+)"', body)
        fields = dict(_re.findall(r'name="([^"]+)"\s+value="([^"]*)"', body))
        if not action:
            raise SystemExit(f"Drive returned a page with no download form "
                             f"for id={file_id}")
        fields.setdefault("id", file_id)
        fields.setdefault("export", "download")
        fields.setdefault("confirm", "t")
        r = session.get(action.group(1).replace("&amp;", "&"), params=fields,
                        stream=True, timeout=120)
        if "text/html" in (r.headers.get("Content-Type") or "").lower():
            r.close()
            raise SystemExit(f"Drive kept serving a page rather than the file "
                             f"(id={file_id})")

    total = 0
    with open(tmp, "wb") as fh:
        for chunk in r.iter_content(1024 * 1024):
            if chunk:
                fh.write(chunk)
                total += len(chunk)
    r.close()
    if total == 0:
        os.remove(tmp)
        raise SystemExit(f"Empty download for id={file_id}")
    os.replace(tmp, out_path)
    return out_path


def fetch_docx_from_drive(language, persona, set_no, dest_dir):
    """Download <Language>/<Persona>/<Language>_<Persona>_Set<n>.docx from the conversation-docs Drive folder; fall back to local export runs if the set is not on."""
    import gdown

    want_lang, want_persona = _norm(language), _norm(persona)

    print(f"Listing conversation-docs Drive folder for "
          f"{language.title()} / {persona.replace('_', ' ').title()} / Set{set_no} ...")
    try:
        files = gdown.download_folder(url=DOCS_DRIVE_URL, skip_download=True, quiet=True)
    except Exception as e:
        # Drive listings fail transiently (rate limits, one unshared subfolder). The local export copies are the same docs -- use them rather than dying.
        print(f"[WARN] Could not list the docs Drive folder ({str(e).splitlines()[0][:120]})")
        local = find_docx_locally(language, persona, set_no)
        if local:
            print(f"Using the local copy instead:\n  {local}")
            return local
        raise SystemExit(
            f"Drive listing failed AND no local copy of "
            f"{language.title()}_{persona.title()}_Set{set_no}.docx exists in exports/. "
            "Retry in a few minutes, or check the docs folder is shared as "
            "'Anyone with the link'.")

    target, candidates = None, []
    for f in files or []:
        base = os.path.basename(f.path.replace("\\", "/"))
        m = DOCX_NAME_RE.match(base)
        if not m:
            continue
        if _norm(m.group(1)) == want_lang and _norm(m.group(2)) == want_persona:
            candidates.append(int(m.group(3)))
            if int(m.group(3)) == int(set_no):
                target = f
    if target is None:
        local = find_docx_locally(language, persona, set_no)
        if local:
            print(f"Set{set_no} not on Drive; using local copy from a past export run:\n  {local}")
            return local
        have = ", ".join(str(n) for n in sorted(candidates)) or "none"
        raise SystemExit(
            f"Set{set_no} not found on Drive for {language}/{persona} "
            f"(and no local copy in exports/auto_docs). Available sets on Drive: {have}"
        )

    os.makedirs(dest_dir, exist_ok=True)
    out_path = os.path.join(dest_dir, os.path.basename(target.path.replace("\\", "/")))
    print(f"Downloading {target.path} (id={target.id}) ...")
    _download_drive_file(target.id, out_path)
    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        raise SystemExit(f"Download failed for {target.path}")
    print(f"Downloaded -> {out_path}")
    return out_path


# Input gathering
def gather_docx(input_path):
    """Yield (display_name, Document) for every docx in a file/dir/zip."""
    if os.path.isdir(input_path):
        paths = []
        for root, _, files in os.walk(input_path):
            for n in sorted(files):
                if n.endswith(".docx") and not n.startswith("~$"):
                    paths.append(os.path.join(root, n))
        for p in paths:
            yield p, Document(p)
    elif input_path.endswith(".docx"):
        yield input_path, Document(input_path)
    elif zipfile.is_zipfile(input_path):
        with zipfile.ZipFile(input_path, "r") as zf:
            names = [n for n in zf.namelist()
                     if n.endswith(".docx") and not n.startswith("__MACOSX")]
            for name in sorted(names):
                with zf.open(name) as f:
                    yield name, Document(io.BytesIO(f.read()))
    else:
        raise SystemExit(f"Unsupported input: {input_path!r} (need .docx, folder, or .zip)")


def parse_docx_name(name):
    """'Telugu_Calm_Explainer_Set5.docx' -> ('telugu', 'calm_explainer', 5)."""
    m = DOCX_NAME_RE.match(os.path.basename(name))
    if not m:
        return None
    return m.group(1).lower(), m.group(2).lower().replace(" ", "_"), int(m.group(3))


# Main
def main():
    p = argparse.ArgumentParser(
        description="Convert conversation DOCX sets to recording Excel files "
                    "(two sheets, <Lg>_ prefixed IDs, Drive-tracked set numbering)."
    )
    p.add_argument("input_path", nargs="?", help=".docx file, folder of docx, or .zip")
    p.add_argument("-l", "--language", help="Fetch from Drive: language (e.g. telugu)")
    p.add_argument("-p", "--persona", help="Fetch from Drive: persona (e.g. storyteller)")
    p.add_argument("-s", "--set", type=int, dest="set_no",
                   help="Fetch from Drive: docx set number to convert")
    p.add_argument("-o", "--output-dir", help="Output directory (default: exports/excel_runs/run_<timestamp>)")
    p.add_argument("--sync-state", action="store_true",
                   help="Rewrite the Excel state CSV from a live Drive listing and exit")
    args = p.parse_args()

    if args.sync_state:
        sync_state_from_drive()
        return

    drive_args = (args.language, args.persona, args.set_no)
    if any(a is not None for a in drive_args):
        if not all(a is not None for a in drive_args):
            p.error("Drive fetch needs all three of --language, --persona and --set")
        if args.input_path:
            p.error("Give either an input_path or --language/--persona/--set, not both")
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        src_dir = os.path.join(RUNS_DIR, f"run_{ts}", "source_docx")
        args.input_path = fetch_docx_from_drive(
            args.language, args.persona, args.set_no, src_dir
        )
        if not args.output_dir:
            args.output_dir = os.path.dirname(src_dir)
    if not args.input_path:
        p.error("input_path is required (unless using --sync-state or -l/-p/-s)")

    docs = list(gather_docx(args.input_path))
    if not docs:
        raise SystemExit("No .docx files found in the input.")

    # Stable ordering so consecutive set numbers follow the input docx order
    docs.sort(key=lambda d: (parse_docx_name(d[0]) or ("", "", 0)))

    state = load_state()
    print("Checking last Excel set numbers (state CSV + live Drive listing)...")
    drive_sets = drive_last_sets()
    for key, n in drive_sets.items():
        if state.get(key, 0) < n:
            state[key] = n

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_dir or os.path.join(RUNS_DIR, f"run_{ts}")

    written = 0
    for name, doc in docs:
        parsed = parse_docx_name(name)
        if not parsed:
            print(f"[SKIP] {os.path.basename(name)}: filename does not match <Lang>_<Persona>_Set<n>.docx")
            continue
        language, persona, src_set = parsed
        lang_title = language.title()
        lang_code = lang_title[:2]  # two-letter prefix: En, Te, Hi, ...

        conversations = parse_doc(doc)
        turns = sum(len(c["turns"]) for c in conversations)
        if not conversations:
            print(f"[SKIP] {os.path.basename(name)}: no conversations parsed")
            continue

        set_no = state.get((language, persona), 0) + 1
        persona_title = "_".join(w.title() for w in persona.split("_"))
        out_name = f"{lang_title}_{persona_title}_Set{set_no}.xlsx"
        dest_dir = os.path.join(out_dir, lang_title)
        os.makedirs(dest_dir, exist_ok=True)
        out_path = os.path.join(dest_dir, out_name)

        wb = build_workbook(conversations, lang_code)
        wb.save(out_path)
        state[(language, persona)] = set_no
        save_state(state)
        written += 1
        print(f"[OK] {os.path.basename(name)} -> {lang_title}/{out_name} "
              f"({len(conversations)} conversations, {turns} turns, IDs like {lang_code}_Conv_1_T_1)")
        # Stable marker for wrapper scripts (e.g. the local scp launcher)
        print(f"XLSX_FILE={out_path}")

    if not written:
        raise SystemExit("Nothing was converted.")
    print(f"\nDone: {written} Excel file(s) in {out_dir}")
    print(f"Set-number state: {STATE_CSV}")
    print(f"RUN_XLSX_DIR={out_dir}")


if __name__ == "__main__":
    main()
