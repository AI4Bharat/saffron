"""Load benchmark verification tasks into the DB."""
import os
import sys
import json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tasks/tts/benchmark_tasks")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "200"))
TEST_TYPE = "benchmark-verification"

LANG_NAMES = {
    "bn": "Bengali", "gu": "Gujarati", "hi": "Hindi", "kn": "Kannada",
    "ml": "Malayalam", "mr": "Marathi", "or": "Odia", "ta": "Tamil",
    "te": "Telugu", "ur": "Urdu", "en": "English",
}


def batch_name(lang, n):
    """The required task name, e.g. benchmark_hi_batch1 (1-indexed)."""
    return f"benchmark_{lang}_batch{n}"


def name_from_description(desc):
    """Extract the benchmark_<lang>_batch<n> token from a stored description."""
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


def load_language(lang, existing_by_name):
    path = os.path.join(BENCHMARK_DIR, f"{lang}.jsonl")
    if not os.path.exists(path):
        print(f"[SKIP] No file for '{lang}' at {path}")
        return 0

    items = read_jsonl(path)
    if not items:
        print(f"[SKIP] {lang}.jsonl is empty")
        return 0

    lang_name = LANG_NAMES.get(lang, lang.capitalize())
    n_batches = (len(items) + BATCH_SIZE - 1) // BATCH_SIZE
    print(f"\n=== {lang} ({lang_name}): {len(items)} items -> {n_batches} batch(es) of up to {BATCH_SIZE} ===")

    created = 0
    for i in range(n_batches):
        n = i + 1
        chunk = items[i * BATCH_SIZE:(i + 1) * BATCH_SIZE]
        name = batch_name(lang, n)
        description = f"{name} — {lang_name}"

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
        created += 1
    return created


def main():
    langs = [a.strip().lower() for a in sys.argv[1:] if a.strip()]
    if not langs:
        langs = sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(BENCHMARK_DIR)
            if f.endswith(".jsonl")
        )
        print(f"No language given; loading all: {', '.join(langs)}")

    with app.app_context():
        # Pre-index existing benchmark Tests by their name token so reloads update.
        existing_by_name = {}
        for t in Test.query.filter_by(test_type=TEST_TYPE).all():
            existing_by_name[name_from_description(t.description)] = t

        total = 0
        for lang in langs:
            total += load_language(lang, existing_by_name)

    print(f"\nDone. {total} batch Test row(s) created/updated.")


if __name__ == "__main__":
    main()
