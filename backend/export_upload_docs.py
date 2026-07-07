#!/usr/bin/env python3
"""
export_upload_docs.py — one-command conversation delivery pipeline.

Given a language and a version, this script:
  1. Finds all matching `conversation-editable` tests in the backend DB.
  2. Exports their rated/edited annotations to JSONL (reuses export_conversations.py).
     Defaults: accepted conversations only, without comments
     (override with --include-all / --any-comments / --with-comments).
  3. Generates persona DOCX files with at most 30 conversations per set
     (reuses generate_docs.py), numbering sets from the last uploaded set + 1.
  4. Uploads the DOCX files to Google Drive under <Language>/<Persona>/.
  5. Tracks the last uploaded set number per (language, persona) in a CSV.

The last-set number is taken as max(state CSV, live Drive listing) so numbering
never collides even if the CSV falls out of date. Existing Drive files are NEVER
overwritten: if a target filename already exists in the destination folder the
upload is skipped and reported.

Usage:
    venv/bin/python export_upload_docs.py --language telugu --version 5
    venv/bin/python export_upload_docs.py -l hindi -v new           # "New Version"
    venv/bin/python export_upload_docs.py -l marathi -v base        # no version suffix
    venv/bin/python export_upload_docs.py -l odia -v 5 --dry-run    # plan only
    venv/bin/python export_upload_docs.py -l odia -v 5 --no-upload  # generate docs only

Drive upload requires a Google service account JSON key. Default location:
    /root/saffron/backend/config/gdrive_service_account.json
(override with --sa-file or the GDRIVE_SA_FILE env var). The Drive folder must be
shared with the service account's email address as Editor.
"""

import argparse
import csv
import datetime
import json
import os
import re
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BACKEND_DIR)

from main import app
from application.models import Test
from export_conversations import export_conversation_ratings, slugify
from generate_docs import build_persona_documents, PERSONA_ORDER

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
DRIVE_ROOT_FOLDER_ID = "15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk"
DRIVE_ROOT_URL = f"https://drive.google.com/drive/folders/{DRIVE_ROOT_FOLDER_ID}"
STATE_CSV = os.path.join(BACKEND_DIR, "upload_sets_state.csv")
RUNS_DIR = os.path.join(BACKEND_DIR, "exports", "auto_docs")
DEFAULT_SA_FILE = os.environ.get(
    "GDRIVE_SA_FILE", os.path.join(BACKEND_DIR, "config", "gdrive_service_account.json")
)
CHUNK_SIZE = 30  # max conversations per DOCX set

DOCX_NAME_RE = re.compile(r"^(?P<prefix>.+)_Set(?P<num>\d+)\.docx$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Test discovery
# ---------------------------------------------------------------------------
def version_predicate(version):
    """Return (label, predicate) matching test descriptions for the requested version."""
    v = str(version).strip().lower().replace("_", " ")
    if v in ("new", "new version"):
        return "New Version", lambda d: " - new version" in d.lower()
    if v in ("base", "none", "original", "1"):
        rx = re.compile(r" - (version \d+|new version)", re.IGNORECASE)
        return "base (no version suffix)", lambda d: not rx.search(d)
    if v.isdigit():
        rx = re.compile(rf" - version {v}(\D|$)", re.IGNORECASE)
        return f"Version {v}", lambda d: bool(rx.search(d))
    raise SystemExit(f"Unrecognized version '{version}'. Use a number, 'new', or 'base'.")


def desc_persona(description):
    """'Conversation Editable - Telugu - Warm Encourager - ...' -> 'warm_encourager'"""
    parts = [s.strip() for s in (description or "").split(" - ")]
    return parts[2].lower().replace(" ", "_") if len(parts) > 2 else ""


def find_tests(language, version, personas_filter=None):
    label, pred = version_predicate(version)
    prefix = f"conversation editable - {language.strip().lower()} - "
    with app.app_context():
        tests = Test.query.filter(Test.test_type == "conversation-editable").all()
        matches = [
            (t.id, t.description, len(t.json_entry) if isinstance(t.json_entry, list) else 0)
            for t in tests
            if (t.description or "").lower().startswith(prefix)
            and pred(t.description or "")
            and (personas_filter is None or desc_persona(t.description) in personas_filter)
        ]
    matches.sort(key=lambda x: x[0])
    return label, matches


# ---------------------------------------------------------------------------
# Set-number state (CSV + live Drive listing)
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


def drive_all_last_sets():
    """Scan the shared Drive folder (anonymous, read-only) for the highest existing
    Set number per (language, persona). Returns {} if the listing fails."""
    result = {}
    try:
        import gdown

        files = gdown.download_folder(url=DRIVE_ROOT_URL, skip_download=True, quiet=True)
        for f in files or []:
            parts = f.path.replace("\\", "/").split("/")
            if len(parts) < 3:
                continue
            m = DOCX_NAME_RE.match(parts[-1])
            if not m:
                continue
            lang = parts[0].strip().lower().replace(" ", "_")
            persona = parts[1].strip().lower().replace(" ", "_")
            key = (lang, persona)
            result[key] = max(result.get(key, 0), int(m.group("num")))
    except Exception as e:
        print(f"[WARN] Could not list Drive folder for last-set detection: {e}")
    return result


def drive_last_sets(language):
    lang = language.strip().lower()
    return {p: n for (l, p), n in drive_all_last_sets().items() if l == lang}


def sync_state_from_drive():
    """Rewrite the state CSV to mirror the live Drive listing exactly (all languages)."""
    drive_sets = drive_all_last_sets()
    if not drive_sets:
        raise SystemExit("Drive listing returned nothing; state CSV left untouched.")
    save_state(drive_sets)
    print(f"State CSV rewritten from Drive: {len(drive_sets)} (language, persona) pairs. "
          f"-> {STATE_CSV}")
    for (lang, persona), n in sorted(drive_sets.items()):
        print(f"  {lang:<10} {persona:<22} last_set = {n}")


def effective_start_sets(language, state, drive_sets):
    """Per persona: next set number = max(CSV, Drive) + 1."""
    lang = language.strip().lower()
    starts, sources = {}, {}
    for persona in PERSONA_ORDER:
        csv_last = state.get((lang, persona), 0)
        drv_last = drive_sets.get(persona, 0)
        last = max(csv_last, drv_last)
        starts[persona] = last + 1
        sources[persona] = f"csv={csv_last}, drive={drv_last}"
    return starts, sources


# ---------------------------------------------------------------------------
# Google Drive upload (service account)
# ---------------------------------------------------------------------------
def get_drive_service(sa_file):
    if not os.path.exists(sa_file):
        raise SystemExit(
            f"Service account key not found: {sa_file}\n"
            "One-time setup:\n"
            "  1. In Google Cloud Console create a service account and download its JSON key.\n"
            "  2. Enable the 'Google Drive API' for that project.\n"
            f"  3. Copy the key to {sa_file} (or pass --sa-file / set GDRIVE_SA_FILE).\n"
            "  4. Share the Drive folder with the service account email as Editor.\n"
            "Or run with --no-upload to only generate the DOCX files."
        )
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        sa_file, scopes=["https://www.googleapis.com/auth/drive"]
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_children(service, folder_id, folders_only=False):
    q = f"'{folder_id}' in parents and trashed = false"
    if folders_only:
        q += " and mimeType = 'application/vnd.google-apps.folder'"
    items, token = [], None
    while True:
        resp = (
            service.files()
            .list(q=q, fields="nextPageToken, files(id, name, mimeType)",
                  pageToken=token, pageSize=1000, supportsAllDrives=True,
                  includeItemsFromAllDrives=True)
            .execute()
        )
        items.extend(resp.get("files", []))
        token = resp.get("nextPageToken")
        if not token:
            return items


def find_subfolder(service, parent_id, name, create=False):
    """Case/format-insensitive folder lookup ('warm_encourager' matches 'Warm Encourager')."""
    want = re.sub(r"[\s_]+", " ", name.strip().lower())
    for f in list_children(service, parent_id, folders_only=True):
        have = re.sub(r"[\s_]+", " ", f["name"].strip().lower())
        if have == want:
            return f["id"], f["name"], False
    if not create:
        return None, None, False
    title = name.replace("_", " ").title()
    meta = {"name": title, "mimeType": "application/vnd.google-apps.folder", "parents": [parent_id]}
    created = service.files().create(body=meta, fields="id, name", supportsAllDrives=True).execute()
    return created["id"], created["name"], True


def upload_docx(service, folder_id, local_path):
    """Upload a .docx; returns (status, file_id). Never overwrites an existing file."""
    from googleapiclient.http import MediaFileUpload

    name = os.path.basename(local_path)
    existing = [f for f in list_children(service, folder_id) if f["name"] == name]
    if existing:
        return "exists", existing[0]["id"]
    media = MediaFileUpload(
        local_path,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        resumable=True,
    )
    meta = {"name": name, "parents": [folder_id]}
    created = service.files().create(
        body=meta, media_body=media, fields="id", supportsAllDrives=True
    ).execute()
    return "uploaded", created["id"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    p = argparse.ArgumentParser(
        description="Export rated conversations for a language+version, build persona "
                    "DOCX sets (max 30 conversations each) and upload them to Google Drive."
    )
    p.add_argument("--language", "-l", help="e.g. telugu, hindi, odia")
    p.add_argument("--version", "-v",
                   help="e.g. 5, or 'new' (New Version), or 'base' (no version suffix)")
    p.add_argument("--sync-state", action="store_true",
                   help="Refresh the state CSV from a live Drive listing (all languages) and exit")
    p.add_argument("--include-all", action="store_true",
                   help="Include rejected and unrated conversations too "
                        "(default: only conversations marked as accepted)")
    p.add_argument("--with-comments", action="store_true",
                   help="Export only conversations that have comments")
    p.add_argument("--any-comments", action="store_true",
                   help="Include conversations with and without comments "
                        "(default: only conversations WITHOUT comments)")
    p.add_argument("--chunk-size", type=int, default=CHUNK_SIZE,
                   help=f"Max conversations per DOCX set (default {CHUNK_SIZE})")
    p.add_argument("--personas", help="Comma-separated persona filter (e.g. storyteller,relatable_peer)")
    p.add_argument("--sa-file", default=DEFAULT_SA_FILE,
                   help="Google service account JSON key for Drive upload")
    p.add_argument("--create-missing-folders", action="store_true",
                   help="Create the Language/Persona folder on Drive if it does not exist")
    p.add_argument("--no-upload", action="store_true",
                   help="Generate DOCX files but skip Drive upload and CSV state update")
    p.add_argument("--dry-run", action="store_true",
                   help="Show matched tests and planned set numbers, then exit")
    args = p.parse_args()

    if args.sync_state:
        sync_state_from_drive()
        return
    if not args.language or not args.version:
        p.error("--language and --version are required (unless using --sync-state)")

    language = args.language.strip().lower()
    only_accepted = not args.include_all
    comments_filter = "with" if args.with_comments else ("all" if args.any_comments else "without")
    personas_filter = None
    if args.personas:
        personas_filter = {s.strip().lower() for s in args.personas.split(",") if s.strip()}
        unknown = personas_filter - set(PERSONA_ORDER)
        if unknown:
            raise SystemExit(f"Unknown persona(s): {', '.join(sorted(unknown))}")

    # 1. Find tests -----------------------------------------------------------
    label, tests = find_tests(language, args.version, personas_filter)
    if not tests:
        raise SystemExit(f"No conversation-editable tests found for {language.title()} / {label}.")
    print(f"Found {len(tests)} test(s) for {language.title()} / {label}:")
    for tid, desc, n in tests:
        print(f"  {tid}  ({n} tasks)  {desc}")

    # 2. Determine next set numbers ------------------------------------------
    state = load_state()
    print("\nChecking last uploaded set numbers (state CSV + live Drive listing)...")
    drive_sets = drive_last_sets(language)
    starts, sources = effective_start_sets(language, state, drive_sets)
    for persona in PERSONA_ORDER:
        if personas_filter and persona not in personas_filter:
            continue
        print(f"  {persona:<22} next set = {starts[persona]:>3}  ({sources[persona]})")

    if args.dry_run:
        print("\n[DRY RUN] No export, DOCX generation, or upload performed.")
        return

    # 3. Export JSONL ---------------------------------------------------------
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, f"{language}_{slugify(label)}_{ts}")
    jsonl_dir = os.path.join(run_dir, "jsonl")
    docx_dir = os.path.join(run_dir, "docx")
    os.makedirs(jsonl_dir, exist_ok=True)
    print(f"\nExporting {len(tests)} test(s) to {jsonl_dir} "
          f"(only_accepted={only_accepted}, comments={comments_filter})")
    for tid, desc, _ in tests:
        out = os.path.join(jsonl_dir, f"{tid}_conversation-editable_{slugify(desc or str(tid))}.jsonl")
        export_conversation_ratings(tid, out, only_accepted, comments_filter)

    # 4. Generate DOCX sets ---------------------------------------------------
    print(f"\nGenerating DOCX files (max {args.chunk_size} conversations per set)...")
    written = build_persona_documents(
        jsonl_dir,
        docx_dir,
        language=language,
        chunk_size=args.chunk_size,
        personas_to_process=personas_filter,
        persona_start_sets=starts,
    )
    if not written:
        raise SystemExit("No DOCX files were generated (no matching conversations in export).")

    # Arrange files in an upload-ready tree: docx/<Language>/<Persona>/<file>.docx
    lang_title = language.replace("_", " ").title()
    arranged = []
    for persona, path, count in written:
        persona_title = persona.replace("_", " ").title()
        dest_dir = os.path.join(docx_dir, lang_title, persona_title)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(path))
        os.replace(path, dest)
        arranged.append((persona, dest, count))
        print(f"  {lang_title}/{persona_title}/{os.path.basename(dest)}  ({count} conversations)")
    written = arranged
    # Stable marker for wrapper scripts (e.g. the local pull-to-laptop launcher)
    print(f"RUN_DOCX_DIR={docx_dir}")

    def bump_state(state):
        for persona, path, _ in written:
            m = DOCX_NAME_RE.match(os.path.basename(path))
            if m and state.get((language, persona), 0) < int(m.group("num")):
                state[(language, persona)] = int(m.group("num"))
        save_state(state)

    if args.no_upload:
        bump_state(state)
        print(f"\n--no-upload: DOCX files left in {docx_dir} (arranged Language/Persona).")
        print(f"State CSV updated to the generated set numbers: {STATE_CSV}")
        print(f"Pull to your machine with:\n  scp -r tts-labelstudio:{docx_dir}/* <local_folder>/")
        return

    # 5. Upload to Drive ------------------------------------------------------
    print("\nUploading to Google Drive...")
    service = get_drive_service(args.sa_file)
    lang_id, lang_name, created = find_subfolder(
        service, DRIVE_ROOT_FOLDER_ID, language, create=args.create_missing_folders
    )
    if not lang_id:
        raise SystemExit(f"Language folder '{language.title()}' not found on Drive. "
                         "Re-run with --create-missing-folders to create it.")
    if created:
        print(f"  Created language folder '{lang_name}' on Drive.")

    persona_folder_cache = {}
    uploaded, skipped, failed = [], [], []
    for persona, path, count in written:
        if persona not in persona_folder_cache:
            pid, pname, pcreated = find_subfolder(
                service, lang_id, persona, create=args.create_missing_folders
            )
            if pcreated:
                print(f"  Created persona folder '{pname}' on Drive.")
            persona_folder_cache[persona] = pid
        folder_id = persona_folder_cache[persona]
        name = os.path.basename(path)
        if not folder_id:
            failed.append((name, "persona folder missing on Drive (use --create-missing-folders)"))
            continue
        try:
            status, file_id = upload_docx(service, folder_id, path)
        except Exception as e:
            failed.append((name, str(e)))
            continue
        m = DOCX_NAME_RE.match(name)
        set_no = int(m.group("num")) if m else None
        if status == "exists":
            skipped.append((name, file_id))
            print(f"  [SKIP] {name} already exists on Drive (id={file_id}) — not overwritten.")
        else:
            uploaded.append((name, file_id))
            print(f"  [OK]   {name} -> {lang_name}/{persona.replace('_', ' ').title()} (id={file_id})")
        # Advance the CSV either way: the set number is taken on Drive.
        if set_no is not None:
            key = (language, persona)
            if state.get(key, 0) < set_no:
                state[key] = set_no
                save_state(state)

    # 6. Summary ---------------------------------------------------------------
    print(f"\nDone. Uploaded {len(uploaded)}, skipped {len(skipped)} (already existed), "
          f"failed {len(failed)}.")
    if failed:
        for name, err in failed:
            print(f"  [FAIL] {name}: {err}")
        sys.exit(1)
    print(f"Local copies: {docx_dir}")
    print(f"Set-number state: {STATE_CSV}")


if __name__ == "__main__":
    main()
