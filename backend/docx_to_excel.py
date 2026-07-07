#!/usr/bin/env python3
"""
docx_to_excel.py — convert conversation DOCX sets into recording Excel files.

Takes a single .docx, a directory of .docx files, or a .zip of .docx files and
produces one .xlsx per doc with two sheets:

  Sheet "Turns":          ID | Speaker | Dialogue     (ID: <Lg>_Conv_N_T_M)
  Sheet "Conversations":  ID | Conversation           (ID: <Lg>_Conv_N)

<Lg> is the two-letter language prefix (En, Te, Hi, ...) — PREFIX, not suffix.

Output files are named <Language>_<Persona>_Set<n>.xlsx where n continues from
the last set uploaded to the Excel Drive folder, tracked in a state CSV
(excel_sets_state.csv) and cross-checked against a live Drive listing —
the same mechanism as the conversation docs pipeline. Files are arranged in
<output_dir>/<Language>/ subfolders.

Usage:
    venv/bin/python docx_to_excel.py <docx | folder | zip>
    venv/bin/python docx_to_excel.py exports/auto_docs/<run>/docx
    venv/bin/python docx_to_excel.py --sync-state      # reset CSV from Drive
"""

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

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
EXCEL_DRIVE_FOLDER_ID = "1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"
EXCEL_DRIVE_URL = f"https://drive.google.com/drive/folders/{EXCEL_DRIVE_FOLDER_ID}"
STATE_CSV = os.path.join(BACKEND_DIR, "excel_sets_state.csv")
RUNS_DIR = os.path.join(BACKEND_DIR, "exports", "excel_runs")

DOCX_NAME_RE = re.compile(r"^([A-Za-z]+)_(.+)_Set(\d+)\.docx$", re.IGNORECASE)
XLSX_NAME_RE = re.compile(r"^(?:copy of )?([A-Za-z]+)_(.+)_Set(\d+)\.xlsx$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# DOCX parsing (IDs use the two-letter language PREFIX, e.g. En_Conv_1_T_1)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Workbook building (yellow theme)
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Set-number state (CSV + live Drive listing) — same mechanism as the docs
# ---------------------------------------------------------------------------
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
    """Highest existing Set number per (language, persona) in the Excel Drive
    folder, parsed from the xlsx filenames. {} if the listing fails."""
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


# ---------------------------------------------------------------------------
# Input gathering
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Convert conversation DOCX sets to recording Excel files "
                    "(two sheets, <Lg>_ prefixed IDs, Drive-tracked set numbering)."
    )
    p.add_argument("input_path", nargs="?", help=".docx file, folder of docx, or .zip")
    p.add_argument("-o", "--output-dir", help="Output directory (default: exports/excel_runs/run_<timestamp>)")
    p.add_argument("--sync-state", action="store_true",
                   help="Rewrite the Excel state CSV from a live Drive listing and exit")
    args = p.parse_args()

    if args.sync_state:
        sync_state_from_drive()
        return
    if not args.input_path:
        p.error("input_path is required (unless using --sync-state)")

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

    if not written:
        raise SystemExit("Nothing was converted.")
    print(f"\nDone: {written} Excel file(s) in {out_dir}")
    print(f"Set-number state: {STATE_CSV}")
    print(f"RUN_XLSX_DIR={out_dir}")


if __name__ == "__main__":
    main()
