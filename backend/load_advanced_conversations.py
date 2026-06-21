"""Load the leftover ADVANCED conversation batches (conversations_<lang>.jsonl).

These were never uploaded (only Elementary + Secondary/NCERT conversations were).
Each is aligned with the English source conversations.jsonl exactly like the other
conversation batches (load_jsonl_config injects per-turn english + *_en fields) and
loaded as a `translation-correction` Test so it renders with the existing page.

Idempotent (skips a description that already exists); never deletes anything.

Usage (saffron backend venv):
    python load_advanced_conversations.py --dry-run
    python load_advanced_conversations.py
"""
import os, sys, argparse

sys.path.append('/root/saffron/backend')
os.chdir('/root/saffron/backend')
from main import app
from application.database import db
from application.models import Test
from load_jsonl import load_jsonl_config

DASH = '/data/dashboard'
ENGLISH = os.path.join(DASH, 'conversations.jsonl')
BATCH = 250
LANGUAGES = ["bengali", "gujarati", "hindi", "kannada", "malayalam",
             "marathi", "odia", "tamil", "telugu", "urdu"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default=",".join(LANGUAGES))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    langs = [l.strip().lower() for l in args.languages.split(",") if l.strip()]

    with app.app_context():
        existing = {t.description for t in Test.query.with_entities(Test.description).all()}
        next_id = (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1
        created = skipped = total = 0
        for lang in langs:
            path = os.path.join(DASH, f"conversations_{lang}.jsonl")
            if not os.path.exists(path):
                print(f"  [skip] no file for {lang}")
                continue
            data = load_jsonl_config(path, ENGLISH)
            n = len(data)
            nb = (n + BATCH - 1) // BATCH
            prefix = f"Advanced {lang.capitalize()} Translation"
            for i in range(nb):
                chunk = data[i * BATCH:(i + 1) * BATCH]
                start, end = i * BATCH + 1, i * BATCH + len(chunk)
                desc = f"{prefix} - Part {i+1} (Tasks {start} to {end})"
                if desc in existing:
                    skipped += 1
                    continue
                total += len(chunk)
                if args.dry_run:
                    print(f"  [dry] would create id={next_id} '{desc}' ({len(chunk)} tasks)")
                else:
                    db.session.add(Test(id=next_id, test_type="translation-correction",
                                        description=desc, json_entry=chunk))
                    db.session.commit()
                    print(f"  created id={next_id} '{desc}' ({len(chunk)} tasks)")
                existing.add(desc)
                next_id += 1
                created += 1
        print(f"\n{'DRY-RUN ' if args.dry_run else ''}done: {created} batch(es), "
              f"{skipped} existed, {total} tasks.")


if __name__ == "__main__":
    main()
