#!/usr/bin/env python3
"""Load the aivanta transcript-correction clips as Test batches.

One logical task (96 Hindi clips, each with a machine transcript) split into N
equal batches. Annotators hear the clip and correct the transcript line by line,
so each item carries the transcript pre-split into the lines the UI edits.

  ./venv/bin/python loaders/load_transcript_correction_tasks.py --dry-run
  ./venv/bin/python loaders/load_transcript_correction_tasks.py --batches 2
"""

import argparse
import json
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

# Deliberately NOT 'from main import app': importing the app runs the migration
# suite, whose ALTER TABLE statements take an ACCESS EXCLUSIVE lock on rater and
# stall every request behind them. A loader only needs to INSERT, so it talks to
# the database directly.
import sqlalchemy as sa

TASK_DIR = os.path.join(BACKEND_DIR, 'aivanta_task')
MANIFEST = os.path.join(TASK_DIR, 'manifest.jsonl')
TEST_TYPE = 'transcript-correction'
TASK_NAME = 'Aivanta Hindi Transcript Correction'
TEAM_KEY = os.environ.get('TRANSCRIPT_TEAM_KEY', 'tts')


def _engine():
    uri = None
    with open(os.path.join(BACKEND_DIR, '.env'), encoding='utf-8') as f:
        for line in f:
            if line.startswith('DATABASE_URI'):
                uri = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not uri:
        raise SystemExit('DATABASE_URI not found in backend/.env')
    return sa.create_engine(uri)


def load_manifest():
    rows = []
    with open(MANIFEST, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _closest_subset(sizes, target):
    """Domain names whose sizes sum as close to target as possible without exceeding it."""
    best = (0, ())
    names = list(sizes)
    for mask in range(1 << len(names)):
        chosen = [names[i] for i in range(len(names)) if mask >> i & 1]
        total = sum(sizes[c] for c in chosen)
        if total <= target and total > best[0]:
            best = (total, tuple(chosen))
    return best[1]


def split_into_batches(rows, n_batches):
    """Equal-sized batches that keep each domain whole wherever the arithmetic allows.

    Domains are whole blocks; we look for a subset of them summing exactly to the
    batch size and, failing that, take the closest subset under it and top the
    batch up from one more domain. Only that one domain ends up straddling.
    """
    per = len(rows) // n_batches
    if per * n_batches != len(rows):
        raise SystemExit(f'{len(rows)} clips do not divide into {n_batches} equal batches.')

    by_domain = {}
    for r in rows:
        by_domain.setdefault(r['audio_filename'].split('/')[1], []).append(r)

    remaining = {d: list(items) for d, items in by_domain.items()}
    batches = []
    for _ in range(n_batches - 1):
        sizes = {d: len(v) for d, v in remaining.items() if v}
        picked = []
        for d in _closest_subset(sizes, per):
            picked.extend(remaining.pop(d))
        short = per - len(picked)
        if short:
            # Top up from the largest domain left, in manifest order, so the
            # clips that straddle stay contiguous.
            donor = max((d for d, v in remaining.items() if v), key=lambda d: len(remaining[d]))
            picked.extend(remaining[donor][:short])
            remaining[donor] = remaining[donor][short:]
        batches.append(picked)
    batches.append([r for v in remaining.values() for r in v])
    return batches


def to_item(row, index):
    text = row.get('text') or ''
    lines = text.split('\n')
    return {
        'id': index,
        'audio_filename': row['audio_filename'],
        'title': row.get('title') or '',
        'domain': row.get('domain') or '',
        'speaker': row.get('speaker') or '',
        'language': row.get('language') or 'hi',
        'duration': row.get('duration'),
        'sample_rate': row.get('sample_rate'),
        # The transcript as one string and pre-split into the lines the UI edits.
        'text': text,
        'lines': lines,
        'n_lines': len(lines),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--batches', type=int, default=2)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    rows = load_manifest()
    missing = [r for r in rows if not os.path.isfile(r['audio_filepath'])]
    if missing:
        raise SystemExit(f'{len(missing)} manifest rows point at audio that is not on disk.')
    print(f'Manifest: {len(rows)} clips, all audio present.')

    batches = split_into_batches(rows, args.batches)
    engine = _engine()
    md = sa.MetaData()
    test_t = sa.Table('test', md, autoload_with=engine)
    team_t = sa.Table('team', md, autoload_with=engine)

    with engine.begin() as conn:
        team_id = conn.execute(
            sa.select(team_t.c.id).where(team_t.c.key == TEAM_KEY)).scalar()
        if team_id is None:
            raise SystemExit(f'No team with key {TEAM_KEY!r}.')

        item_no = 0
        for i, batch in enumerate(batches, start=1):
            items = []
            for r in batch:
                item_no += 1
                items.append(to_item(r, item_no))
            description = f'{TASK_NAME} - Batch {i} of {len(batches)} ({len(items)} clips)'

            mins = sum(it['duration'] or 0 for it in items) / 60
            counts = {}
            for it in items:
                d = it['audio_filename'].split('/')[1]
                counts[d] = counts.get(d, 0) + 1
            print()
            print(f'Batch {i}: {len(items)} clips, {mins:.0f} min')
            for d in sorted(counts):
                print(f'    {counts[d]:3d}  {d}')

            if args.dry_run:
                continue

            existing = conn.execute(sa.select(test_t.c.id).where(
                sa.and_(test_t.c.test_type == TEST_TYPE,
                        test_t.c.description == description))).scalar()
            # handoff_mode is NOT NULL and its default lives on the model, not in
            # the table, so writing outside the ORM has to state it.
            values = dict(test_type=TEST_TYPE, description=description,
                          json_entry=items, team_id=team_id,
                          item_count=len(items), language_hint='hindi',
                          handoff_mode=False)
            if existing:
                conn.execute(sa.update(test_t).where(test_t.c.id == existing).values(**values))
                print(f'    updated existing Test id={existing}')
            else:
                new_id = conn.execute(
                    sa.insert(test_t).values(**values).returning(test_t.c.id)).scalar()
                print(f'    created Test id={new_id}')

    if args.dry_run:
        print()
        print('Dry run - nothing written.')


if __name__ == '__main__':
    main()
