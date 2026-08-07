#!/usr/bin/env python3
"""Load the ASR text-review sheet into the pool as ONE upload."""

import argparse
import os
import re
import sys
import tempfile
import urllib.request

import openpyxl

# The backend root (where main.py and application/ live), regardless of cwd.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import app                                   # noqa: E402  (pushes app context)
from application.models import db, Team, PoolItem, PoolUpload   # noqa: E402

# Sheet columns -> pool_item fields. Anything else on the row is kept in extra_json.
COLUMN_MAP = {
    'language': 'language',
    'class': 'class_label',
    'category': 'category',
    'difficulty': 'source_difficulty',
    'text': 'text',
    'n_words': 'n_words',
    'source': 'source',
}


def sheet_export_url(url):
    """Turn any Google Sheets URL into its .xlsx export URL."""
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9-_]+)', url)
    if not m:
        return url
    return f'https://docs.google.com/spreadsheets/d/{m.group(1)}/export?format=xlsx'


def download(url):
    dest = os.path.join(tempfile.gettempdir(), 'asr_pool_source.xlsx')
    print(f'downloading {url}')
    with urllib.request.urlopen(url, timeout=180) as r, open(dest, 'wb') as fh:
        fh.write(r.read())
    print(f'  saved {os.path.getsize(dest):,} bytes -> {dest}')
    return dest


def clean(value):
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def read_rows(path):
    """Every data row of every tab, as dicts keyed by the (lower-cased) header."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    rows = []
    for name in wb.sheetnames:
        ws = wb[name]
        it = ws.iter_rows(values_only=True)
        try:
            header = [str(h).strip().lower() if h is not None else '' for h in next(it)]
        except StopIteration:
            continue
        n = 0
        for raw in it:
            if raw is None or all(v is None or str(v).strip() == '' for v in raw):
                continue
            row = {header[i]: raw[i] for i in range(min(len(header), len(raw)))}
            row['_tab'] = name
            rows.append(row)
            n += 1
        print(f'  tab "{name}": {n:,} row(s)')
    return rows


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument('--url', help='Google Sheets URL (must be link-viewable)')
    src.add_argument('--file', help='local .xlsx')
    ap.add_argument('--team', default='asr')
    ap.add_argument('--name', default='ASR text review - 100hr 6 languages')
    ap.add_argument('--task-type', default='text-review',
                    help='what kind of work these items are (shown in every export)')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--batch', type=int, default=2000)
    args = ap.parse_args()

    path = args.file if args.file else download(sheet_export_url(args.url))
    print('reading workbook...')
    rows = read_rows(path)
    print(f'{len(rows):,} data row(s) total')
    if not rows:
        print('nothing to load')
        return 1

    with app.app_context():
        team = Team.query.filter_by(key=args.team).first()
        if team is None:
            print(f'ERROR: no team with key "{args.team}". Start the app once so the '
                  'migrations seed the teams, or create it from the admin UI.')
            return 2
        if team.workflow != 'pool':
            print(f'ERROR: team "{team.key}" is not a pool team (workflow={team.workflow}).')
            return 2

        # Existing items, so a re-run only adds what is genuinely new.
        existing = set()
        for lang, text in db.session.query(PoolItem.language, PoolItem.text).filter(
                PoolItem.team_id == team.id).yield_per(5000):
            existing.add((lang, text))
        print(f'{len(existing):,} item(s) already in the {team.name} pool')

        prepared, skipped, dupes = [], 0, 0
        seen_in_file = set()
        for row in rows:
            fields = {}
            extra = {}
            for key, value in row.items():
                if key == '_tab':
                    continue
                target = COLUMN_MAP.get(key)
                if target:
                    fields[target] = clean(value)
                elif value is not None and str(value).strip():
                    extra[key] = clean(value)

            text = (fields.get('text') or '').strip()
            language = (fields.get('language') or row.get('_tab') or '').strip()
            if not text or not language:
                skipped += 1
                continue
            if (language, text) in existing or (language, text) in seen_in_file:
                dupes += 1
                continue
            seen_in_file.add((language, text))

            n_words = fields.get('n_words')
            try:
                n_words = int(float(n_words)) if n_words not in (None, '') else None
            except (TypeError, ValueError):
                n_words = None

            prepared.append(dict(
                team_id=team.id,
                task_type=args.task_type,
                language=language,
                class_label=fields.get('class_label'),
                category=(fields.get('category') or '').lower() or None,
                source_difficulty=(fields.get('source_difficulty') or None),
                source=fields.get('source'),
                n_words=n_words,
                text=text,
                extra_json=extra or None,
                status='available',
            ))

        print(f'\nto insert : {len(prepared):,}')
        print(f'duplicates: {dupes:,} (already in the pool or repeated in the file)')
        print(f'unusable  : {skipped:,} (no text / no language)')

        by_lang = {}
        for p in prepared:
            by_lang[p['language']] = by_lang.get(p['language'], 0) + 1
        for lang in sorted(by_lang):
            print(f'   {lang:<12} {by_lang[lang]:>7,}')

        if args.dry_run:
            print('\n--dry-run: nothing written.')
            return 0
        if not prepared:
            print('\nnothing new to load.')
            return 0

        upload = PoolUpload(team_id=team.id, name=args.name,
                            source=args.url or args.file, item_count=len(prepared))
        db.session.add(upload)
        db.session.flush()

        for i in range(0, len(prepared), args.batch):
            chunk = prepared[i:i + args.batch]
            db.session.bulk_insert_mappings(
                PoolItem, [dict(c, upload_id=upload.id) for c in chunk])
            db.session.commit()
            print(f'  inserted {min(i + args.batch, len(prepared)):,}/{len(prepared):,}')

        # Create/refresh the task layer for whatever was just loaded, so new (language, class, task-type) slices appear as tasks without waiting for a restart.
        from application.migrations import sync_pool_tasks
        sync_pool_tasks()

        total = db.session.query(db.func.count(PoolItem.id)).filter(
            PoolItem.team_id == team.id).scalar()
        print(f'\nDONE. {team.name} pool now holds {total:,} item(s) '
              f'(upload #{upload.id}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
