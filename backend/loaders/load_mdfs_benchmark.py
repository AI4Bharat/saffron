#!/usr/bin/env python3
"""Load the 7-language TTS benchmark into the ASR pool as MDFS rating work.

One prompt per CSV row: the paragraph as the text, the voice-converted audio as
the thing to listen to. They join the MDFS tasks that already exist, one per
language, so annotators already assigned to those tasks pick this up with no
further setup.

Every column of the CSV is kept on the item so nothing is lost on the way in --
including audio_status and qc_status, so the rows flagged upstream can be told
apart later even though they are being rated like the rest.

    python load_mdfs_benchmark.py --dry-run
    python load_mdfs_benchmark.py
"""
import argparse
import os
os.environ["SAFFRON_SKIP_BOOT_MIGRATIONS"] = "1"
import csv
import sys
from collections import Counter, defaultdict

sys.path.insert(0, "/root/saffron/backend")

from main import app
from application.database import db
from application.models import Team, PoolItem, PoolTask, PoolUpload

CSV_PATH = "/data2/mdfs_benchmark/benchmark_final_7lang.csv"
AUDIO_PREFIX = "tasks/asr/mdfs_benchmark"
UPLOAD_NAME = "MDFS TTS benchmark (7 languages)"
BATCH = 500

# the CSV's language values -> the language the MDFS tasks already use
LANG_MAP = {
    "english_direct": "English",
    "hindi": "Hindi",
    "kannada": "Kannada",
    "marathi": "Marathi",
    "odia": "Odia",
    "tamil": "Tamil",
    "telugu": "Telugu",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = list(csv.DictReader(open(CSV_PATH, encoding="utf-8")))
    print("  rows in the CSV: %d" % len(rows))

    with app.app_context():
        team = Team.query.filter_by(key="asr").first()
        tasks = {t.language: t for t in PoolTask.query.filter_by(
            team_id=team.id, task_type="audio-mdfs").all()}
        print("  MDFS tasks already present: %s" % ", ".join(sorted(tasks)))

        # what is already in the pool, so a re-run adds only what is new
        existing = set()
        for (extra,) in db.session.query(PoolItem.extra_json).filter(
                PoolItem.team_id == team.id,
                PoolItem.task_type == "audio-mdfs").yield_per(2000):
            if isinstance(extra, dict) and extra.get("clip_id"):
                existing.add(extra["clip_id"])
        print("  MDFS clips already in the pool: %d" % len(existing))

        prepared = []
        skipped = Counter()
        seen = set()
        per_lang = Counter()

        for r in rows:
            raw_lang = (r.get("language") or "").strip()
            lang = LANG_MAP.get(raw_lang)
            if lang is None:
                skipped["unknown language"] += 1
                continue
            task = tasks.get(lang)
            if task is None:
                skipped["no MDFS task for %s" % lang] += 1
                continue

            clip_id = (r.get("clip_id") or "").strip()
            text = (r.get("paragraph_text") or "").strip()
            src = (r.get("vc_audio_path") or "").strip()
            if not clip_id or not text or not src:
                skipped["missing clip_id/text/audio"] += 1
                continue
            if clip_id in existing or clip_id in seen:
                skipped["already loaded"] += 1
                continue

            name = os.path.basename(src)
            local = "/data2/mdfs_benchmark/%s/%s" % (raw_lang, name)
            if not os.path.isfile(local):
                skipped["audio not on the host"] += 1
                continue
            seen.add(clip_id)
            per_lang[lang] += 1

            # every remaining column travels with the item, so nothing the CSV
            # knows is lost once it is in the pool
            extra = {k: v for k, v in r.items()
                     if k not in ("paragraph_text",) and (v or "").strip()}
            extra["audio"] = "%s/%s/%s" % (AUDIO_PREFIX, raw_lang, name)
            extra["clip_id"] = clip_id
            extra["source_csv"] = os.path.basename(CSV_PATH)

            prepared.append(dict(
                team_id=team.id,
                task_id=task.id,
                task_type="audio-mdfs",
                language=lang,
                class_label=task.class_label,
                category=(r.get("audio_status") or "").strip().lower() or None,
                text=text,
                source="tts-benchmark-7lang",
                extra_json=extra,
                status="available",
            ))

        print()
        print("  to insert: %d" % len(prepared))
        for lang, n in sorted(per_lang.items()):
            print("     %-10s %d" % (lang, n))
        if skipped:
            print("  skipped:")
            for why, n in skipped.most_common():
                print("     %-28s %d" % (why, n))

        if args.dry_run:
            print("\n  --dry-run: nothing written.")
            return 0
        if not prepared:
            print("\n  nothing new to load.")
            return 0

        upload = PoolUpload(team_id=team.id, name=UPLOAD_NAME,
                            source=CSV_PATH, item_count=len(prepared))
        db.session.add(upload)
        db.session.flush()

        for i in range(0, len(prepared), BATCH):
            chunk = prepared[i:i + BATCH]
            db.session.bulk_insert_mappings(
                PoolItem, [dict(c, upload_id=upload.id) for c in chunk])
            db.session.commit()
            print("  inserted %d/%d" % (min(i + BATCH, len(prepared)), len(prepared)))

        # refresh the denormalised per-task counts
        from application.migrations import sync_pool_tasks
        sync_pool_tasks()

        from sqlalchemy import func
        total = db.session.query(func.count(PoolItem.id)).filter(
            PoolItem.team_id == team.id, PoolItem.task_type == "audio-mdfs").scalar()
        print()
        print("  DONE. upload #%d, MDFS now holds %d prompt(s)." % (upload.id, total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
