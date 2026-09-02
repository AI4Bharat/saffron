#!/usr/bin/env python3
"""export_upload_docs.py — one-command conversation delivery pipeline."""

import argparse
import csv
import datetime
import json
import os
import re
import sys

# This script lives in backend/exporters/, so the backend root is one level up.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BACKEND_DIR)

from main import app
from application.models import Test
from application.database import db
from export_conversations import export_conversation_ratings, slugify
from generate_docs import build_persona_documents, PERSONA_ORDER

# CONFIGURATION
DRIVE_ROOT_FOLDER_ID = "15NnqyQ4FBqW9Hs7N47mIakCWGvj1_nQk"
DRIVE_ROOT_URL = f"https://drive.google.com/drive/folders/{DRIVE_ROOT_FOLDER_ID}"
STATE_CSV = os.path.join(BACKEND_DIR, "state/upload_sets_state.csv")
VERSION_CSV = os.path.join(BACKEND_DIR, "state/version_state.csv")
RUNS_DIR = os.path.join(BACKEND_DIR, "exports", "auto_docs")
DEFAULT_SA_FILE = os.environ.get(
    "GDRIVE_SA_FILE", os.path.join(BACKEND_DIR, "config", "gdrive_service_account.json")
)
CHUNK_SIZE = 30  # max conversations per DOCX set

# All non-English languages are sourced from the annotation DB. English is special: it is NOT annotated in saffron — its conversations are taken straight from.
ALL_DB_LANGUAGES = ["hindi", "kannada", "marathi", "odia", "tamil", "telugu"]
CONV_EDITABLE_ROOT = os.path.join(BACKEND_DIR, "tasks/tts/conversation_editable_tasks")

DOCX_NAME_RE = re.compile(r"^(?P<prefix>.+)_Set(?P<num>\d+)\.docx$", re.IGNORECASE)


def english_version_dir(version):
    """Source dir of English conversation JSONL for a version: numeric N -> conversation_editable_tasks/version_N ; 'new' -> new_version."""
    v = str(version).strip().lower().replace(" ", "_")
    sub = "new_version" if v in ("new", "new_version") else f"version_{v}"
    return os.path.join(CONV_EDITABLE_ROOT, sub)


# Test discovery
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
        # Only id/description/item_count are needed here. Selecting whole Test rows
        # pulls every json_entry across the wire (the test table is ~240 MB of JSON),
        # which cost ~5.6s per call on PostgreSQL; this costs ~2ms. item_count is the
        # stored length of json_entry -- json_entry is read only for rows missing it.
        rows = (db.session.query(Test.id, Test.description, Test.item_count)
                .filter(Test.test_type == "conversation-editable")
                .filter(Test.description.ilike(prefix + "%"))
                .all())
        rows = [(tid, desc, cnt) for tid, desc, cnt in rows
                if pred(desc or "")
                and (personas_filter is None or desc_persona(desc) in personas_filter)]
        stale = [tid for tid, _, cnt in rows if cnt is None]
        if stale:
            entries = dict(
                (t.id, len(t.json_entry) if isinstance(t.json_entry, list) else 0)
                for t in Test.query.filter(Test.id.in_(stale)).all()
            )
        else:
            entries = {}
        matches = [(tid, desc, entries.get(tid, cnt) or 0) for tid, desc, cnt in rows]
    matches.sort(key=lambda x: x[0])
    return label, matches


# Set-number state (CSV + live Drive listing)
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


# Version state (CSV only — versions are not encoded on Drive)
def load_version_state():
    st = {}
    if os.path.exists(VERSION_CSV):
        with open(VERSION_CSV, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                try:
                    st[row["language"].strip().lower()] = int(row["last_version"])
                except (KeyError, ValueError):
                    continue
    return st


def save_version_state(st):
    tmp = VERSION_CSV + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["language", "last_version", "updated_at"])
        for lang, v in sorted(st.items()):
            w.writerow([lang, v, datetime.datetime.now().isoformat(timespec="seconds")])
    os.replace(tmp, VERSION_CSV)


def drive_all_last_sets():
    """Scan the shared Drive folder (anonymous, read-only) for the highest existing Set number per (language, persona)."""
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


def drive_last_sets_for(language, all_drive):
    lang = language.strip().lower()
    return {p: n for (l, p), n in all_drive.items() if l == lang}


def sync_state_from_drive():
    """Raise the state CSV to match Drive. Never lowers a number.

    The Drive listing is anonymous and therefore partial: it sees only publicly
    shared files, and a failed listing is warned about rather than raised. So a
    number coming back smaller than what the CSV already holds means the
    listing missed something, not that sets disappeared. Taking the max keeps a
    bad listing from handing the next export a set number already in use.
    """
    drive_sets = drive_all_last_sets()
    if not drive_sets:
        raise SystemExit("Drive listing returned nothing; state CSV left untouched.")
    state = load_state()
    raised, kept = [], []
    for key, n in drive_sets.items():
        have = state.get(key, 0)
        if n > have:
            state[key] = n
            raised.append((key, have, n))
        elif n < have:
            kept.append((key, have, n))
    save_state(state)
    print(f"State CSV synced with Drive: {len(drive_sets)} pair(s) seen, "
          f"{len(raised)} raised, {len(kept)} kept ahead of Drive. -> {STATE_CSV}")
    for (lang, persona), old, new in sorted(raised):
        print(f"  {lang:<10} {persona:<22} {old} -> {new}")
    for (lang, persona), have, drv in sorted(kept):
        print(f"  [kept] {lang:<10} {persona:<22} csv={have} > drive={drv} "
              f"(listing is anonymous and may not see recent uploads)")


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


# Generation (shared by both modes)
def export_and_build(language, version, run_dir, next_set,
                     only_accepted, comments_filter, chunk_size, personas_filter):
    """One (language, version): produce the JSONL for that language+version, build persona DOCX into run_dir/docx/<Lang>/<Persona>/, and advance next_set (per."""
    if language == "english":
        label = "New Version" if str(version).strip().lower().replace(" ", "_") in ("new", "new_version") else f"Version {version}"
        jsonl_dir = english_version_dir(version)
        if not os.path.isdir(jsonl_dir):
            print(f"  [English / {label}] source dir not found (skip): {jsonl_dir}")
            return label, []
        print(f"  [English / {label}] source JSONL dir: {jsonl_dir} (filtered to English)")
    else:
        label, tests = find_tests(language, version, personas_filter)
        if not tests:
            return label, []
        print(f"  [{language.title()} / {label}] {len(tests)} test(s): "
              f"{', '.join(str(t[0]) for t in tests)}")
        jsonl_dir = os.path.join(run_dir, "jsonl", f"{language}_{slugify(label)}")
        os.makedirs(jsonl_dir, exist_ok=True)
        for tid, desc, _ in tests:
            out = os.path.join(jsonl_dir, f"{tid}_conversation-editable_{slugify(desc or str(tid))}.jsonl")
            export_conversation_ratings(tid, out, only_accepted, comments_filter)

    tmp_docx = os.path.join(run_dir, "_tmp", f"{language}_{slugify(label)}")
    os.makedirs(tmp_docx, exist_ok=True)
    written_raw = build_persona_documents(
        jsonl_dir, tmp_docx, language=language, chunk_size=chunk_size,
        personas_to_process=personas_filter, persona_start_sets=dict(next_set),
    )

    docx_dir = os.path.join(run_dir, "docx")
    lang_title = language.replace("_", " ").title()
    written = []
    for persona, path, count in written_raw:
        persona_title = persona.replace("_", " ").title()
        dest_dir = os.path.join(docx_dir, lang_title, persona_title)
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, os.path.basename(path))
        os.replace(path, dest)
        m = DOCX_NAME_RE.match(os.path.basename(dest))
        set_no = int(m.group("num")) if m else None
        if set_no is not None:
            next_set[persona] = max(next_set.get(persona, 1), set_no + 1)
        written.append((persona, dest, count, set_no))
        print(f"    {lang_title}/{persona_title}/{os.path.basename(dest)}  ({count} conversations)")
    return label, written


def bump_set_state(state, language, written):
    for persona, _dest, _count, set_no in written:
        if set_no is not None and state.get((language, persona), 0) < set_no:
            state[(language, persona)] = set_no


# Google Drive upload (service account)
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


def upload_language(service, language, written, state, create_missing):
    """Upload one language's arranged DOCX files to Drive; advance set state. Returns counts."""
    lang_id, lang_name, created = find_subfolder(
        service, DRIVE_ROOT_FOLDER_ID, language, create=create_missing
    )
    if not lang_id:
        raise SystemExit(f"Language folder '{language.title()}' not found on Drive. "
                         "Re-run with --create-missing-folders to create it.")
    if created:
        print(f"  Created language folder '{lang_name}' on Drive.")

    persona_folder_cache = {}
    uploaded, skipped, failed = [], [], []
    for persona, path, _count, set_no in written:
        if persona not in persona_folder_cache:
            pid, pname, pcreated = find_subfolder(service, lang_id, persona, create=create_missing)
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
        if status == "exists":
            skipped.append((name, file_id))
            print(f"  [SKIP] {name} already exists on Drive (id={file_id}) — not overwritten.")
        else:
            uploaded.append((name, file_id))
            print(f"  [OK]   {name} -> {lang_name}/{persona.replace('_', ' ').title()} (id={file_id})")
        if set_no is not None and state.get((language, persona), 0) < set_no:
            state[(language, persona)] = set_no
            save_state(state)
    return uploaded, skipped, failed


# CLI helpers
def build_opts(args):
    only_accepted = not args.include_all
    comments_filter = "with" if args.with_comments else ("all" if args.any_comments else "without")
    personas_filter = None
    if args.personas:
        personas_filter = {s.strip().lower() for s in args.personas.split(",") if s.strip()}
        unknown = personas_filter - set(PERSONA_ORDER)
        if unknown:
            raise SystemExit(f"Unknown persona(s): {', '.join(sorted(unknown))}")
    return only_accepted, comments_filter, personas_filter


def next_sync_reminder():
    print("\nNEXT STEPS:")
    print("  1. Upload the DOCX (arranged Language/Persona) to the Drive docs folder.")
    print(f"  2. Then sync SET numbers from Drive:  {sys.executable} export_upload_docs.py --sync-state")
    print("  (VERSION numbers were updated automatically in version_state.csv.)")


# Modes
def run_single(args, only_accepted, comments_filter, personas_filter):
    language = args.language.strip().lower()
    label, tests = find_tests(language, args.version, personas_filter)
    if not tests:
        raise SystemExit(f"No conversation-editable tests found for {language.title()} / {label}.")
    print(f"Found {len(tests)} test(s) for {language.title()} / {label}:")
    for tid, desc, n in tests:
        print(f"  {tid}  ({n} tasks)  {desc}")

    state = load_state()
    all_drive = drive_all_last_sets()
    print("\nChecking last uploaded set numbers (state CSV + live Drive listing)...")
    starts, sources = effective_start_sets(language, state, drive_last_sets_for(language, all_drive))
    for persona in PERSONA_ORDER:
        if personas_filter and persona not in personas_filter:
            continue
        print(f"  {persona:<22} next set = {starts[persona]:>3}  ({sources[persona]})")

    if args.dry_run:
        print("\n[DRY RUN] No export, DOCX generation, or upload performed.")
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, f"{language}_{slugify(label)}_{ts}")
    next_set = dict(starts)
    print(f"\nExporting + generating (only_accepted={only_accepted}, comments={comments_filter})...")
    _, written = export_and_build(language, args.version, run_dir, next_set,
                                  only_accepted, comments_filter, args.chunk_size, personas_filter)
    if not written:
        raise SystemExit("No DOCX files were generated (no matching conversations in export).")

    docx_dir = os.path.join(run_dir, "docx")
    print(f"RUN_DOCX_DIR={docx_dir}")
    bump_set_state(state, language, written)

    vstate = load_version_state()
    if str(args.version).isdigit():
        vstate[language] = max(vstate.get(language, 0), int(args.version))

    if args.no_upload:
        save_state(state)
        save_version_state(vstate)
        print(f"\n--no-upload: DOCX files left in {docx_dir} (arranged Language/Persona).")
        print(f"Pull to your machine with:\n  scp -r tts-labelstudio:{docx_dir}/* <local_folder>/")
        next_sync_reminder()
        return

    print("\nUploading to Google Drive...")
    service = get_drive_service(args.sa_file)
    uploaded, skipped, failed = upload_language(service, language, written, state,
                                                args.create_missing_folders)
    save_state(state)
    save_version_state(vstate)
    print(f"\nDone. Uploaded {len(uploaded)}, skipped {len(skipped)} (already existed), "
          f"failed {len(failed)}.")
    if failed:
        for name, err in failed:
            print(f"  [FAIL] {name}: {err}")
        sys.exit(1)
    print(f"Local copies: {docx_dir}")


def run_range(args, only_accepted, comments_filter, personas_filter):
    # Compose the language list from the selectors (order preserved, de-duplicated):
    languages = []
    if args.languages:
        languages += [l.strip().lower() for l in args.languages.split(",") if l.strip()]
    if args.all_languages:
        languages += ALL_DB_LANGUAGES
    if args.english and "english" not in languages:
        languages.append("english")
    seen, ordered = set(), []
    for l in languages:
        if l not in seen:
            seen.add(l); ordered.append(l)
    languages = ordered
    end_v = args.end_version
    if end_v < 2:
        raise SystemExit("--end-version must be >= 2 (versions start at 2; use single mode for base/new).")

    state = load_state()
    vstate = load_version_state()
    all_drive = drive_all_last_sets()

    # Plan
    plan = []  # (language, last_v, [versions])
    print("Range plan (per language: last uploaded version -> versions to generate):")
    for language in languages:
        last_v = vstate.get(language)
        seeded = last_v is not None
        if not seeded:
            last_v = 1
        versions = list(range(last_v + 1, end_v + 1))
        note = "" if seeded else "  [WARN no version_state, assuming last=1; edit version_state.csv]"
        if not versions:
            print(f"  {language.title():<10} at v{last_v} >= end v{end_v}: SKIP (nothing new){note}")
        else:
            print(f"  {language.title():<10} at v{last_v} -> generate v{versions}{note}")
        plan.append((language, last_v, versions))

    if args.dry_run:
        print("\n[DRY RUN] next set numbers per language:")
        for language, _last, versions in plan:
            if not versions:
                continue
            starts, sources = effective_start_sets(language, state, drive_last_sets_for(language, all_drive))
            for persona in PERSONA_ORDER:
                if personas_filter and persona not in personas_filter:
                    continue
                print(f"  {language.title():<10} {persona:<22} next set = {starts[persona]:>3}  ({sources[persona]})")
        print("\n[DRY RUN] No export, DOCX generation, or upload performed.")
        return

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = os.path.join(RUNS_DIR, f"range_{ts}")
    all_written = []  # (language, [(persona,dest,count,set_no)...])
    any_docs = False

    for language, last_v, versions in plan:
        if not versions:
            continue
        starts, _ = effective_start_sets(language, state, drive_last_sets_for(language, all_drive))
        next_set = dict(starts)
        produced = []
        lang_written = []
        for v in versions:
            _, written = export_and_build(language, str(v), run_dir, next_set,
                                          only_accepted, comments_filter, args.chunk_size, personas_filter)
            if written:
                produced.append(v)
                any_docs = True
                bump_set_state(state, language, written)
                lang_written.extend(written)
            else:
                print(f"    [none] {language.title()} version {v}: no matching "
                      f"accepted/comment-free conversations (skipped).")
        if lang_written:
            all_written.append((language, lang_written))
        if produced:
            vstate[language] = max(last_v, max(produced))
            print(f"  -> {language.title()} version_state advanced to {vstate[language]}.")

    if not any_docs:
        raise SystemExit("No DOCX files were generated for any requested language/version.")

    docx_dir = os.path.join(run_dir, "docx")
    print(f"RUN_DOCX_DIR={docx_dir}")

    if args.no_upload:
        save_state(state)
        save_version_state(vstate)
        print(f"\n--no-upload: DOCX files left in {docx_dir} (arranged Language/Persona).")
        print(f"Pull to your machine with:\n  scp -r tts-labelstudio:{docx_dir}/* <local_folder>/")
        next_sync_reminder()
        return

    print("\nUploading to Google Drive...")
    service = get_drive_service(args.sa_file)
    tot_up = tot_skip = tot_fail = 0
    failures = []
    for language, written in all_written:
        up, sk, fl = upload_language(service, language, written, state, args.create_missing_folders)
        tot_up += len(up); tot_skip += len(sk); tot_fail += len(fl)
        failures.extend(fl)
    save_state(state)
    save_version_state(vstate)
    print(f"\nDone. Uploaded {tot_up}, skipped {tot_skip} (already existed), failed {tot_fail}.")
    if failures:
        for name, err in failures:
            print(f"  [FAIL] {name}: {err}")
        sys.exit(1)
    print(f"Local copies: {docx_dir}")


# Main
def main():
    p = argparse.ArgumentParser(
        description="Export rated conversations and build persona DOCX sets (max 30 each), "
                    "continuing set numbers, then optionally upload to Google Drive."
    )
    p.add_argument("--language", "-l", help="[single mode] one language, e.g. telugu")
    p.add_argument("--version", "-v",
                   help="[single mode] e.g. 5, 'new' (New Version), or 'base' (no version suffix)")
    p.add_argument("--languages", help="[range mode] comma-separated languages, e.g. english,odia,hindi")
    p.add_argument("--all-languages", action="store_true", dest="all_languages",
                   help="[range mode] process ALL non-English languages "
                        f"({', '.join(ALL_DB_LANGUAGES)}); add --english to include English too")
    p.add_argument("--english", action="store_true",
                   help="[range mode] include English (sourced from its per-version JSONL dir, "
                        "not the annotation DB)")
    p.add_argument("--end-version", type=int, dest="end_version",
                   help="[range mode] target version; each language generates last_version+1..this")
    p.add_argument("--sync-state", action="store_true",
                   help="Refresh the SET-number CSV from a live Drive listing (all languages) and exit")
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
                   help="Generate DOCX files but skip Drive upload (CSV state is still updated)")
    p.add_argument("--dry-run", action="store_true",
                   help="Show matched tests, versions and planned set numbers, then exit")
    args = p.parse_args()

    if args.sync_state:
        sync_state_from_drive()
        return

    range_mode = bool(args.languages or args.all_languages or args.english or args.end_version is not None)
    if range_mode:
        if not (args.languages or args.all_languages or args.english):
            p.error("range mode needs a language selector: --languages, --all-languages, and/or --english")
        if args.end_version is None:
            p.error("range mode needs --end-version")
        if args.language or args.version:
            p.error("use either single mode (-l/-v) or range mode (--languages/--all-languages/--english), not both")
    else:
        if not args.language or not args.version:
            p.error("give -l/-v (single), or --languages/--end-version (range), or --sync-state")

    only_accepted, comments_filter, personas_filter = build_opts(args)
    if range_mode:
        run_range(args, only_accepted, comments_filter, personas_filter)
    else:
        run_single(args, only_accepted, comments_filter, personas_filter)


if __name__ == "__main__":
    main()
