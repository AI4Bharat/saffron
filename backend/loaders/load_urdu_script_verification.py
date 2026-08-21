#!/usr/bin/env python3
"""Load the Urdu script-verification clips as one TTS test.

Deliberately talks to the database through its own engine and never imports
main: importing it can run the boot migrations, and an ALTER on a live table
takes an ACCESS EXCLUSIVE lock that stalls every request behind it.

Usage:
    python load_urdu_script_verification.py --dry-run
    python load_urdu_script_verification.py
"""
import argparse
import json
import os
import sys

import sqlalchemy as sa

BACKEND = '/root/saffron/backend'
TASK_DIR = f'{BACKEND}/tasks/tts/urdu_script_verification'
MANIFEST = f'{TASK_DIR}/manifest.jsonl'
AUDIO_PREFIX = 'tasks/tts/urdu_script_verification'

TEST_TYPE = 'script-verification'
DESCRIPTION = 'Urdu Script Verification'
TTS_TEAM_ID = 1


def db_uri():
    for line in open(f'{BACKEND}/.env'):
        if line.startswith('DATABASE_URI'):
            return line.split('=', 1)[1].strip().strip('"').strip("'")
    sys.exit('DATABASE_URI not found in .env')


def build_items():
    items, missing = [], []
    for n, line in enumerate(open(MANIFEST, encoding='utf-8'), start=1):
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        rel = r.get('audio_relpath') or ''
        if not rel or not os.path.isfile(os.path.join(TASK_DIR, rel)):
            missing.append(rel or f'line {n}')
            continue
        vid = r.get('video_id') or os.path.splitext(os.path.basename(rel))[0]
        items.append({
            # id is what the rating rows key on, so it must be stable per clip
            'id': vid,
            'video_id': vid,
            'audio_filename': f'{AUDIO_PREFIX}/{rel}',
            'title': r.get('title') or '',
            'channel': r.get('channel') or '',
            'category': r.get('category') or '',
            'language': r.get('language') or '',
            'duration_s': r.get('duration_s'),
            'script': r.get('script') or '',
        })
    return items, missing


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    items, missing = build_items()
    print(f'  clips read      : {len(items)}')
    if missing:
        print(f'  MISSING AUDIO   : {len(missing)} -> {missing[:5]}')
    no_script = [i['id'] for i in items if not i['script']]
    if no_script:
        print(f'  MISSING SCRIPT  : {len(no_script)} -> {no_script[:5]}')
    ids = [i['id'] for i in items]
    if len(set(ids)) != len(ids):
        sys.exit('  duplicate clip ids -- refusing to load')
    print(f'  unique ids      : {len(set(ids))}')
    total_h = sum((i['duration_s'] or 0) for i in items) / 3600.0
    print(f'  total audio     : {total_h:.1f} h')
    print(f'  sample          : {ids[:3]}')

    if args.dry_run:
        print('\n  dry run -- nothing written')
        return

    if not items:
        sys.exit('  nothing to load')

    e = sa.create_engine(db_uri())
    with e.begin() as c:
        existing = c.execute(sa.text(
            'SELECT id FROM test WHERE test_type=:t AND description=:d'),
            {'t': TEST_TYPE, 'd': DESCRIPTION}).scalar()
        if existing:
            print(f'\n  test {existing} already exists with this name -- refusing to '
                  f'create a second one. Delete it first if you meant to reload.')
            return

        # Columns only; let the sequence assign the id rather than max(id)+1,
        # which is what previously let two concurrent inserts collide.
        new_id = c.execute(sa.text(
            'INSERT INTO test (test_type, description, json_entry, handoff_mode, '
            '                  team_id, item_count, language_hint) '
            'VALUES (:t, :d, CAST(:j AS json), false, :team, :n, :lang) '
            'RETURNING id'),
            {'t': TEST_TYPE, 'd': DESCRIPTION,
             'j': json.dumps(items, ensure_ascii=False),
             'team': TTS_TEAM_ID, 'n': len(items), 'lang': 'urdu'}).scalar()

    print(f'\n  created test {new_id}: "{DESCRIPTION}" ({len(items)} clips, TTS team)')
    print(f'  annotators open it at /{new_id}')


if __name__ == '__main__':
    main()
