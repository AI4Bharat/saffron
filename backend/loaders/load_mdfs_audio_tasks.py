#!/usr/bin/env python3
"""Load the MDFS audio-rating tasks (tasks/asr/audio_transcript) into the pool.

One PoolTask per language (task_type 'audio-mdfs', difficulty step off), one
PoolItem per clip. The item's text is the gold sentence; extra_json carries the
audio path (served via /api/audio/tasks/...), the generation metadata and the
intended E/P/S/Pa levels. Idempotent: clips already loaded (by item_key) are
skipped, so the sheet can be re-run after adding files.

Talks to the database DIRECTLY (no `import main`): importing main runs the boot
migration ALTERs, whose ACCESS EXCLUSIVE locks stall the live app.
"""

import argparse
import csv
import json
import os
import sys
from datetime import datetime

from dotenv import dotenv_values
from sqlalchemy import create_engine, text

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROOT = os.path.join(BACKEND_DIR, 'tasks', 'asr', 'audio_transcript')
TASK_TYPE = 'audio-mdfs'

csv.field_size_limit(10 * 1024 * 1024)   # style prompts are long


def wav_index(vc_dir):
    """{'<custom_id>_P<profile_id>__': filename} for every wav in the folder."""
    out = {}
    for name in os.listdir(vc_dir):
        if not name.lower().endswith('.wav'):
            continue
        prefix = name.split('__', 1)[0] + '__'
        out.setdefault(prefix, name)
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--team', default='asr', help="pool team key (default: asr)")
    p.add_argument('--root', default=DEFAULT_ROOT,
                   help="folder holding one subdir per language (default: tasks/asr/audio_transcript)")
    p.add_argument('--languages', default='',
                   help="comma-separated subset (default: every language folder found)")
    p.add_argument('--upload-name', default='MDFS audio rating (benchmark anchors)')
    p.add_argument('--dry-run', action='store_true', help="parse and report; write nothing")
    args = p.parse_args()

    uri = dotenv_values(os.path.join(BACKEND_DIR, '.env')).get('DATABASE_URI')
    if not uri:
        sys.exit('DATABASE_URI missing from backend/.env')
    eng = create_engine(uri, connect_args={'connect_timeout': 15})

    langs = sorted(d for d in os.listdir(args.root)
                   if os.path.isdir(os.path.join(args.root, d)))
    if args.languages:
        wanted = {x.strip().lower() for x in args.languages.split(',') if x.strip()}
        langs = [l for l in langs if l.lower() in wanted]
    if not langs:
        sys.exit(f'No language folders found under {args.root}')

    with eng.begin() as c:
        team_id = c.execute(text("SELECT id FROM team WHERE key = :k AND workflow = 'pool'"),
                            {'k': args.team}).scalar()
        if team_id is None:
            sys.exit(f"No pool team with key '{args.team}'")

        existing = {k for (k,) in c.execute(text(
            "SELECT item_key FROM pool_item WHERE team_id = :t AND task_type = :tt"),
            {'t': team_id, 'tt': TASK_TYPE})}

        upload_id = None
        grand = 0
        for lang_dir in langs:
            language = lang_dir.strip().title()
            base = os.path.join(args.root, lang_dir)
            csvs = [f for f in os.listdir(base) if f.endswith('.csv')]
            vc_dirs = [d for d in os.listdir(base)
                       if os.path.isdir(os.path.join(base, d))]
            if len(csvs) != 1 or len(vc_dirs) != 1:
                print(f'[SKIP] {lang_dir}: need exactly one csv + one audio dir '
                      f'(found {csvs} / {vc_dirs})')
                continue
            wavs = wav_index(os.path.join(base, vc_dirs[0]))

            rows, missing_wav, dupes = [], 0, 0
            with open(os.path.join(base, csvs[0]), newline='', encoding='utf-8') as fh:
                for r in csv.DictReader(fh):
                    cid, pid = (r.get('custom_id') or '').strip(), (r.get('profile_id') or '').strip()
                    gold = (r.get('gold_sentence') or '').strip()
                    if not cid or not pid or not gold:
                        continue
                    wav = wavs.get(f'{cid}_P{pid}__')
                    if not wav:
                        missing_wav += 1
                        continue
                    item_key = f'{lang_dir.lower()}:{cid}_P{pid}'
                    if item_key in existing:
                        dupes += 1
                        continue
                    existing.add(item_key)
                    intended = {}
                    for dim, col in (('expression', 'E'), ('phrasing', 'P'),
                                     ('smoothness', 'S'), ('pacing', 'Pa')):
                        try:
                            intended[dim] = int(r.get(col))
                        except (TypeError, ValueError):
                            pass
                    rows.append({
                        'item_key': item_key,
                        'category': (r.get('bucket') or '').strip().lower() or None,
                        'text': gold,
                        'n_words': len(gold.split()),
                        'extra': json.dumps({
                            'audio': f'tasks/asr/audio_transcript/{lang_dir}/{vc_dirs[0]}/{wav}',
                            'custom_id': cid, 'profile_id': pid,
                            'bucket': (r.get('bucket') or '').strip() or None,
                            'generated_text': (r.get('generated_text') or '').strip() or None,
                            'intended': intended or None,
                            'qc_flag': (r.get('qc_flag') or '').strip() or None,
                        }, ensure_ascii=False),
                    })

            print(f'{language}: {len(rows)} new item(s)'
                  + (f', {dupes} already loaded' if dupes else '')
                  + (f', {missing_wav} row(s) without a wav' if missing_wav else ''))
            if not rows or args.dry_run:
                continue

            if upload_id is None:
                upload_id = c.execute(text(
                    "INSERT INTO pool_upload (team_id, name, source, item_count, created_at) "
                    "VALUES (:t, :n, :s, 0, :now) RETURNING id"),
                    {'t': team_id, 'n': args.upload_name, 's': args.root,
                     'now': datetime.utcnow()}).scalar()

            task_id = c.execute(text(
                "SELECT id FROM pool_task WHERE team_id = :t AND language = :l "
                "AND class_label IS NULL AND task_type = :tt"),
                {'t': team_id, 'l': language, 'tt': TASK_TYPE}).scalar()
            if task_id is None:
                task_id = c.execute(text(
                    "INSERT INTO pool_task (team_id, language, class_label, task_type, "
                    "item_count, settings, is_active, created_at) "
                    "VALUES (:t, :l, NULL, :tt, 0, :s, true, :now) RETURNING id"),
                    {'t': team_id, 'l': language, 'tt': TASK_TYPE,
                     's': json.dumps({'difficulty_annotation': False}),
                     'now': datetime.utcnow()}).scalar()

            c.execute(text(
                "INSERT INTO pool_item (team_id, upload_id, item_key, task_type, task_id, "
                "language, class_label, category, source, n_words, text, extra_json, "
                "status, is_edited, is_flagged, revision) "
                "VALUES (:team, :upload, :item_key, :tt, :task, :lang, NULL, :category, "
                "'tts-benchmark', :n_words, :text, CAST(:extra AS json), "
                "'available', false, false, 0)"),
                [{'team': team_id, 'upload': upload_id, 'tt': TASK_TYPE,
                  'task': task_id, 'lang': language, **row} for row in rows])
            c.execute(text(
                "UPDATE pool_task SET item_count = "
                "(SELECT count(*) FROM pool_item WHERE task_id = :task) WHERE id = :task"),
                {'task': task_id})
            grand += len(rows)

        if upload_id is not None:
            c.execute(text(
                "UPDATE pool_upload SET item_count = "
                "(SELECT count(*) FROM pool_item WHERE upload_id = :u) WHERE id = :u"),
                {'u': upload_id})
        print(('DRY RUN — nothing written.' if args.dry_run else
               f'Done: {grand} item(s) loaded into team {args.team!r} as {TASK_TYPE}.'))


if __name__ == '__main__':
    main()
