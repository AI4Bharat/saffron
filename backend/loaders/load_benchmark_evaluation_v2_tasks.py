"""Load the V2 benchmark verification tasks (benchmark_tasks_v2) into the DB."""
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks/tts/benchmark_tasks_v2")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "200"))
TEST_TYPE = "benchmark-evaluation-v2"
NAME_PREFIX = "benchmark_evaluation_v2"
SOURCE_LANG = "en"

# Languages left out of a bare "load everything" run.
SKIP_LANGS = {"en"}

LANG_NAMES = {
    "bn": "Bengali", "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "or": "Odia", "ta": "Tamil",
    "te": "Telugu", "ur": "Urdu", "en": "English",
}


def batch_name(lang, n):
    """The task name, e.g. benchmark_evaluation_v2_hi_batch1 (1-indexed)."""
    return f"{NAME_PREFIX}_{lang}_batch{n}"


def name_from_description(desc):
    """Extract the benchmark_evaluation_v2_<lang>_batch<n> token from a description."""
    return (desc or "").split(" — ")[0].strip()


def read_jsonl(path):
    items = []
    with open(path, "r", encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  [ERROR] {os.path.basename(path)}:{ln} bad JSON: {e}")
                sys.exit(1)
    return items


def load_source_index():
    """id -> English source object, used to resolve each item's `source_id`."""
    path = os.path.join(BENCHMARK_DIR, f"{SOURCE_LANG}.jsonl")
    if not os.path.exists(path):
        print(f"[WARN] No {SOURCE_LANG}.jsonl at {path}; items will carry no English reference.")
        return {}
    index = {o["id"]: o for o in read_jsonl(path) if o.get("id")}
    print(f"Indexed {len(index)} English source sentences from {SOURCE_LANG}.jsonl")
    return index


def attach_reference(item, source_index):
    """Return a copy of `item` with the English source attached under `_ref_*`."""
    src_id = item.get("source_id")
    if not src_id:
        return item
    src = source_index.get(src_id)
    if not src:
        return item
    out = dict(item)
    out["_ref_source_lang"] = src.get("lang") or SOURCE_LANG
    out["_ref_source_raw_text"] = src.get("raw_text")
    out["_ref_source_spoken_form"] = src.get("spoken_form")
    return out


def load_language(lang, source_index, existing_by_name, dry_run=False):
    path = os.path.join(BENCHMARK_DIR, f"{lang}.jsonl")
    if not os.path.exists(path):
        print(f"[SKIP] No file for '{lang}' at {path}")
        return 0

    items = read_jsonl(path)
    if not items:
        print(f"[SKIP] {lang}.jsonl is empty")
        return 0

    # Sanity: every id must be unique within a language, otherwise the per-item rating lookup (keyed by item id) would collide and merge two items' work.
    seen = {}
    for i, o in enumerate(items):
        iid = str(o.get("id"))
        if iid in seen:
            print(f"  [ERROR] {lang}.jsonl duplicate id '{iid}' at lines {seen[iid] + 1} and {i + 1}")
            sys.exit(1)
        seen[iid] = i

    items = [attach_reference(o, source_index) for o in items]
    resolved = sum(1 for o in items if "_ref_source_raw_text" in o)
    expected = sum(1 for o in items if o.get("source_id"))
    if expected and resolved < expected:
        print(f"  [WARN] {expected - resolved} item(s) have a source_id that is not in {SOURCE_LANG}.jsonl")

    lang_name = LANG_NAMES.get(lang, lang.capitalize())
    n_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\n=== {lang} ({lang_name}): {len(items)} items -> {n_batches} batch(es) of up to {BATCH_SIZE} "
          f"| English reference on {resolved}/{len(items)} ===")

    touched = 0
    for i in range(n_batches):
        n = i + 1
        chunk = items[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
        name = batch_name(lang, n)
        description = f"{name} — {lang_name}"

        if dry_run:
            verb = "Would update" if name in existing_by_name else "Would create"
            print(f"  {verb}  {name}  ({len(chunk)} items)")
            touched += 1
            continue

        existing = existing_by_name.get(name)
        if existing:
            existing.json_entry = chunk
            existing.description = description
            existing.test_type = TEST_TYPE
            db.session.commit()
            print(f"  Updated Test #{existing.id}  {name}  ({len(chunk)} items)")
        else:
            # Let SQLite assign the id (autoincrement) to avoid max(id)+1 races.
            test = Test(test_type=TEST_TYPE, description=description, json_entry=chunk)
            db.session.add(test)
            db.session.commit()
            existing_by_name[name] = test
            print(f"  Created Test #{test.id}  {name}  ({len(chunk)} items)")
        touched += 1
    return touched


def main():
    args = [a.strip() for a in sys.argv[1:] if a.strip()]
    dry_run = "--dry-run" in args
    langs = [a.lower() for a in args if not a.startswith("-")]
    if not langs:
        langs = sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(BENCHMARK_DIR)
            if f.endswith(".jsonl")
        )
        skipped = sorted(set(langs) & SKIP_LANGS)
        langs = [l for l in langs if l not in SKIP_LANGS]
        print(f"No language given; loading all: {', '.join(langs)}")
        if skipped:
            print(f"Skipping {', '.join(skipped)} (in SKIP_LANGS; pass the code "
                  f"explicitly to load it anyway).")
    if dry_run:
        print("DRY RUN — nothing will be written to the database.\n")

    source_index = load_source_index()

    with app.app_context():
        # Pre-index existing v2 Tests by their name token so reloads update.
        existing_by_name = {}
        for t in Test.query.filter_by(test_type=TEST_TYPE).all():
            existing_by_name[name_from_description(t.description)] = t

        total = 0
        for lang in langs:
            total += load_language(lang, source_index, existing_by_name, dry_run=dry_run)

    print(f"\nDone. {total} batch Test row(s) {'planned' if dry_run else 'created/updated'}.")


if __name__ == "__main__":
    main()
