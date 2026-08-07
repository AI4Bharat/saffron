#!/usr/bin/env python3
"""Copy the Saffron SQLite database into PostgreSQL, preserving every row and id.

Two-phase use so annotators keep working during the slow bulk copy:
  1. While the app is still on SQLite:   python scripts/migrate_sqlite_to_postgres.py
  2. Stop the app, then recopy the tables that changed meanwhile (everything is
     re-truncated and re-copied, so the result is always a consistent snapshot):
       python scripts/migrate_sqlite_to_postgres.py --tables rater,team_member,rating,message,pool_item,pool_task,pool_task_assignment,pool_pull,pool_upload,admin_user,team
  3. Flip DATABASE_URI in .env to POSTGRES_DATABASE_URI and start the app.

The SQLite file is only ever read. Credentials come from .env (POSTGRES_DATABASE_URI).
"""

import argparse
import os
import sys
import sqlite3
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv                                    # noqa: E402
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

import psycopg2                                                    # noqa: E402
import psycopg2.extras                                             # noqa: E402
from sqlalchemy import create_engine                               # noqa: E402

from application.models import db  # registers every model on db.metadata  # noqa: E402

SQLITE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'instance', 'database.db')

# Parents before children (foreign keys).
TABLE_ORDER = ['team', 'rater', 'admin_user', 'team_member', 'test', 'rating',
               'message', 'pool_upload', 'pool_task', 'pool_task_assignment',
               'pool_pull', 'pool_item']

# Columns stored as 0/1 in SQLite that are real booleans in PostgreSQL.
BOOL_COLUMNS = {
    'team': {'is_active'},
    'rater': {'is_active'},
    'admin_user': {'is_active'},
    'team_member': {'is_active'},
    'test': {'handoff_mode'},
    'message': {'is_read'},
    'pool_task': {'is_active'},
    'pool_task_assignment': {'is_active'},
    'pool_item': {'is_edited', 'is_flagged'},
}

BATCH_BY_TABLE = {'test': 20, 'rating': 500}   # blob-heavy tables go in small bites
DEFAULT_BATCH = 2000


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# Rows whose FK target row no longer exists (SQLite never enforced the FKs). They are invisible to the app; PostgreSQL rejects them, so they are archived to a JSONL file next to the database and skipped -- nothing is silently dropped.
ORPHAN_FILTERS = {
    'rating': 'test_id NOT IN (SELECT id FROM test)',
    'message': 'rater_id NOT IN (SELECT id FROM rater)',
    'team_member': 'rater_id NOT IN (SELECT id FROM rater)',
}
ORPHAN_ARCHIVE = os.path.join(os.path.dirname(SQLITE_PATH), 'orphans_archive.jsonl')


def _archive_orphans(lite, table, cols):
    cond = ORPHAN_FILTERS.get(table)
    if not cond:
        return 0
    import json
    rows = lite.execute(f"SELECT {', '.join(cols)} FROM {table} WHERE {cond}").fetchall()
    if rows:
        with open(ORPHAN_ARCHIVE, 'a', encoding='utf-8') as fh:
            for row in rows:
                fh.write(json.dumps({'table': table, 'row': dict(zip(cols, row))},
                                    ensure_ascii=False, default=str) + '\n')
        log(f'  {table}: archived {len(rows)} orphaned row(s) to {ORPHAN_ARCHIVE}')
    return len(rows)


def copy_table(lite, pg, table):
    cols = [r[1] for r in lite.execute(f'PRAGMA table_info({table})').fetchall()]
    bools = BOOL_COLUMNS.get(table, set())
    bool_idx = [i for i, c in enumerate(cols) if c in bools]
    orphans = _archive_orphans(lite, table, cols)
    not_orphan = f' WHERE NOT ({ORPHAN_FILTERS[table]})' if table in ORPHAN_FILTERS else ''
    total = lite.execute(f'SELECT COUNT(*) FROM {table}{not_orphan}').fetchone()[0]
    col_sql = ', '.join(cols)
    batch = BATCH_BY_TABLE.get(table, DEFAULT_BATCH)

    cur = pg.cursor()
    cur.execute(f'TRUNCATE TABLE {table} RESTART IDENTITY CASCADE')

    read = lite.execute(f'SELECT {col_sql} FROM {table}{not_orphan} ORDER BY id')
    done = 0
    t0 = time.time()
    while True:
        rows = read.fetchmany(batch)
        if not rows:
            break
        if bool_idx:
            rows = [tuple((bool(v) if v is not None else None) if i in bool_idx else v
                          for i, v in enumerate(row)) for row in rows]
        psycopg2.extras.execute_values(
            cur, f'INSERT INTO {table} ({col_sql}) VALUES %s', rows, page_size=batch)
        pg.commit()
        done += len(rows)
        if done % (batch * 10) < batch or done == total:
            rate = done / max(time.time() - t0, 0.001)
            log(f'  {table}: {done:,}/{total:,} rows ({rate:,.0f}/s)')

    cur.execute(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
    pg.commit()
    return done, total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tables', help='comma-separated subset (default: all, in FK order)')
    ap.add_argument('--verify-only', action='store_true')
    args = ap.parse_args()

    pg_uri = os.environ.get('POSTGRES_DATABASE_URI')
    if not pg_uri:
        log('POSTGRES_DATABASE_URI is not set in .env')
        return 2

    wanted = [t.strip() for t in args.tables.split(',')] if args.tables else TABLE_ORDER
    unknown = [t for t in wanted if t not in TABLE_ORDER]
    if unknown:
        log(f'unknown table(s): {unknown}')
        return 2
    # Always copy in FK order regardless of how the subset was written.
    wanted = [t for t in TABLE_ORDER if t in wanted]

    lite = sqlite3.connect(f'file:{SQLITE_PATH}?mode=ro', uri=True)
    pg = psycopg2.connect(pg_uri, connect_timeout=20)

    # 1. Schema from the models -- tables only, no seeds, ids preserved.
    engine = create_engine(pg_uri)
    db.metadata.create_all(engine)
    engine.dispose()
    log('schema ensured on PostgreSQL')

    if not args.verify_only:
        for t in wanted:
            log(f'copying {t} ...')
            done, total = copy_table(lite, pg, t)
            if done != total:
                log(f'  WARNING: {t} copied {done} of {total}')

    # 2. Verify: row counts must match exactly.
    log('verifying row counts (orphaned rows live in the archive file, not PostgreSQL) ...')
    cur = pg.cursor()
    ok = True
    for t in TABLE_ORDER:
        cond = ORPHAN_FILTERS.get(t)
        where = f' WHERE NOT ({cond})' if cond else ''
        want = lite.execute(f'SELECT COUNT(*) FROM {t}{where}').fetchone()[0]
        cur.execute(f'SELECT COUNT(*) FROM {t}')
        got = cur.fetchone()[0]
        mark = 'OK ' if want == got else '** MISMATCH **'
        log(f'  {t:22} sqlite={want:>9,}  postgres={got:>9,}  {mark}')
        ok = ok and want == got

    lite.close()
    pg.close()
    log('DONE' if ok else 'FINISHED WITH MISMATCHES')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
