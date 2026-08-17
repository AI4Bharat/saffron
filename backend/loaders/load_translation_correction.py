#!/usr/bin/env python3
"""Load the class-wise translation-correction sheet into the ASR pool.

The sheet has one tab per class; each row carries an English source sentence and
its translation into every target language. One pool item is created per
(row, target language): the annotator sees the English as read-only reference and
corrects the translation.

  ./venv/bin/python loaders/load_translation_correction.py --dry-run
  ./venv/bin/python loaders/load_translation_correction.py --languages Bengali,Urdu
  ./venv/bin/python loaders/load_translation_correction.py

Talks to the database directly rather than importing main: that import runs the
migration suite, whose ALTER TABLEs take ACCESS EXCLUSIVE locks and stall the app.
"""

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
import urllib.request

import openpyxl
import sqlalchemy as sa

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SHEET_ID = '1QkaSxt3tESCJTHSD0BN22HmslOyQwWUedCAlP7kZhV4'
SHEET_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=xlsx'
LOCAL_COPY = os.path.join(BACKEND_DIR, 'tasks', 'asr', 'pool_source',
                          'translation_correction.xlsx')

TASK_TYPE = 'translation-correction'
UPLOAD_NAME = 'Translation correction (class-wise, English -> target)'
TEAM_KEY = os.environ.get('POOL_TEAM_KEY', 'asr')

# Columns that describe the row rather than being a translation target.
META_COLUMNS = {'class', 'category', 'english'}


def engine():
    uri = None
    with open(os.path.join(BACKEND_DIR, '.env'), encoding='utf-8') as f:
        for line in f:
            if line.startswith('DATABASE_URI'):
                uri = line.split('=', 1)[1].strip().strip('"').strip("'")
    if not uri:
        raise SystemExit('DATABASE_URI not found in backend/.env')
    return sa.create_engine(uri)


def fetch_sheet(path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f'downloading the sheet -> {path}')
    with urllib.request.urlopen(SHEET_URL, timeout=120) as r, open(path, 'wb') as out:
        out.write(r.read())
    return path


def is_meta_column(header):
    """Columns that describe the row rather than being a translation target.

    Matched by prefix, not equality: the Class 4 tab labels its first column
    'Class 4' rather than 'Class', and treating that as a language would invent a
    phantom 'Class 4' language and lose the class for every row on the tab.
    """
    h = (header or '').strip().lower()
    return (not h) or h.startswith('class') or h in META_COLUMNS


def read_rows(path, wanted_languages=None):
    """[(class, category, english, {language: translation})] over every class tab."""
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        if not ws.title.lower().startswith('class'):
            continue          # 'Stats' and any other summary tab
        # The tab name is the authority on which class this is; the in-sheet
        # column is inconsistently labelled.
        digits = ''.join(ch for ch in ws.title if ch.isdigit())
        class_label = digits or ws.title.strip()

        rows = ws.iter_rows(values_only=True)
        header = [str(h).strip() if h is not None else '' for h in next(rows)]
        lang_cols = {i: h for i, h in enumerate(header) if not is_meta_column(h)}
        if wanted_languages:
            lang_cols = {i: h for i, h in lang_cols.items() if h in wanted_languages}
        print(f'  {ws.title}: class {class_label}, languages -> '
              f'{", ".join(sorted(lang_cols.values())) or "(none)"}')
        idx = {h.lower(): i for i, h in enumerate(header) if h}

        for row in rows:
            def cell(name):
                i = idx.get(name)
                v = row[i] if i is not None and i < len(row) else None
                return str(v).strip() if v is not None else ''
            english = cell('english')
            if not english:
                continue      # trailing blank rows
            translations = {}
            for i, lang in lang_cols.items():
                v = row[i] if i < len(row) else None
                v = str(v).strip() if v is not None else ''
                if v:
                    translations[lang] = v
            out.append((class_label, cell('category'), english, translations))
    return out


def item_key(language, class_label, english):
    """Stable per (language, class, source sentence), so re-running never duplicates."""
    h = hashlib.sha1(english.encode('utf-8')).hexdigest()[:12]
    return f'transcorr:{language.lower()}:{class_label}:{h}'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--file', help='xlsx to load (default: download the sheet)')
    ap.add_argument('--languages', help='comma-separated subset of target languages')
    ap.add_argument('--batch', type=int, default=1000)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    path = args.file or (LOCAL_COPY if os.path.isfile(LOCAL_COPY)
                         else fetch_sheet(LOCAL_COPY))
    wanted = {s.strip() for s in args.languages.split(',')} if args.languages else None

    rows = read_rows(path, wanted)
    if not rows:
        raise SystemExit('no usable rows found in the sheet.')

    prepared = []
    for class_label, category, english, translations in rows:
        for language, text in translations.items():
            prepared.append(dict(
                task_type=TASK_TYPE,
                language=language,
                class_label=str(class_label) or None,
                category=(category or '').lower() or None,
                source='translation-sheet',
                n_words=len(text.split()),
                text=text,
                item_key=item_key(language, class_label, english),
                # The English stays reference-only: it is what the annotator reads
                # to judge the translation, never something they edit.
                # A dict, NOT json.dumps: the column is JSON, so a pre-serialised
                # string would be stored as a JSON string and ->>'source_en' would
                # return NULL for every row.
                extra_json={'source_en': english, 'category_label': category},
                status='available',
                is_edited=False, is_flagged=False, revision=0,
            ))

    by_lang, by_class = {}, {}
    for p in prepared:
        by_lang[p['language']] = by_lang.get(p['language'], 0) + 1
        by_class[p['class_label']] = by_class.get(p['class_label'], 0) + 1
    print(f'\nsource rows : {len(rows):,}')
    print(f'pool items  : {len(prepared):,}')
    print('\nby language:')
    for k in sorted(by_lang):
        print(f'   {k:<12} {by_lang[k]:>7,}')
    print('\nby class:')
    for k in sorted(by_class, key=lambda x: (x is None, x)):
        print(f'   class {str(k):<6} {by_class[k]:>7,}')

    eng = engine()
    md = sa.MetaData()
    item_t = sa.Table('pool_item', md, autoload_with=eng)
    task_t = sa.Table('pool_task', md, autoload_with=eng)
    upload_t = sa.Table('pool_upload', md, autoload_with=eng)
    team_t = sa.Table('team', md, autoload_with=eng)

    with eng.begin() as conn:
        team_id = conn.execute(
            sa.select(team_t.c.id).where(team_t.c.key == TEAM_KEY)).scalar()
        if team_id is None:
            raise SystemExit(f'no team with key {TEAM_KEY!r}')

        seen = {r[0] for r in conn.execute(
            sa.select(item_t.c.item_key).where(item_t.c.item_key.isnot(None)))}
        fresh = [p for p in prepared if p['item_key'] not in seen]
        print(f'\nalready loaded: {len(prepared) - len(fresh):,}')
        print(f'to insert     : {len(fresh):,}')

        if args.dry_run:
            print('\n--dry-run: nothing written.')
            return 0
        if not fresh:
            print('\nnothing new to load.')
            return 0

        # Several NOT NULL columns take their default from the SQLAlchemy model
        # rather than the table, so writing outside the ORM has to supply them.
        now = _dt.datetime.utcnow()
        upload_id = conn.execute(sa.insert(upload_t).values(
            team_id=team_id, name=UPLOAD_NAME, source=os.path.relpath(path, BACKEND_DIR),
            item_count=len(fresh), created_at=now).returning(upload_t.c.id)).scalar()

        for i in range(0, len(fresh), args.batch):
            chunk = [dict(c, team_id=team_id, upload_id=upload_id)
                     for c in fresh[i:i + args.batch]]
            conn.execute(sa.insert(item_t), chunk)
            print(f'  inserted {min(i + args.batch, len(fresh)):,}/{len(fresh):,}')

        # Task layer: one task per (language, class, kind of work), same shape as
        # sync_pool_tasks but done here so the loader never imports the app.
        combos = conn.execute(sa.text("""
            SELECT DISTINCT language, class_label FROM pool_item
             WHERE team_id = :t AND task_type = :tt
        """), {'t': team_id, 'tt': TASK_TYPE}).all()
        known = {(r[0], r[1]) for r in conn.execute(sa.text("""
            SELECT language, class_label FROM pool_task
             WHERE team_id = :t AND task_type = :tt
        """), {'t': team_id, 'tt': TASK_TYPE}).all()}
        made = 0
        for language, class_label in combos:
            if (language, class_label) in known:
                continue
            conn.execute(sa.insert(task_t).values(
                team_id=team_id, language=language, class_label=class_label,
                task_type=TASK_TYPE, item_count=0, is_active=True, created_at=now))
            made += 1
        print(f'\ntasks created : {made}')

        linked = conn.execute(sa.text("""
            UPDATE pool_item SET task_id = (
                SELECT t.id FROM pool_task t
                 WHERE t.team_id = pool_item.team_id
                   AND t.language = pool_item.language
                   AND t.class_label IS NOT DISTINCT FROM pool_item.class_label
                   AND t.task_type = pool_item.task_type)
             WHERE task_id IS NULL AND task_type = :tt
        """), {'tt': TASK_TYPE}).rowcount
        print(f'items linked  : {linked:,}')

        conn.execute(sa.text("""
            UPDATE pool_task SET item_count = COALESCE((
                SELECT count(*) FROM pool_item i WHERE i.task_id = pool_task.id), 0)
             WHERE task_type = :tt
        """), {'tt': TASK_TYPE})

        total = conn.execute(sa.text(
            'SELECT count(*) FROM pool_item WHERE team_id=:t AND task_type=:tt'),
            {'t': team_id, 'tt': TASK_TYPE}).scalar()
        print(f'\nDONE. {total:,} translation-correction item(s) in the pool '
              f'(upload #{upload_id}).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
