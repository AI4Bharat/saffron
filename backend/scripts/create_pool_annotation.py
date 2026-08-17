#!/usr/bin/env python3
"""Create pool_annotation and backfill it from the annotations stored inline on
pool_item.

Redundant annotation needs N annotations per prompt, and pool_item can only hold
one (final_text / completed_by are columns on the item). This table holds one row
per (item, annotator) covering both the claim and the submission, so a prompt can
be handed to several people and every answer is kept.

Purely additive: nothing reads this table until the pull/submit paths are changed,
so running it changes no behaviour. Every DDL statement runs under a lock_timeout,
so if it cannot get its lock it fails immediately instead of queueing the whole
application behind it.
"""
import os
import sys

import sqlalchemy as sa

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) \
    if os.path.basename(os.path.dirname(os.path.abspath(__file__))) == 'scripts' \
    else '/root/saffron/backend'

LOCK_TIMEOUT = os.environ.get('SAFFRON_LOCK_TIMEOUT', '3s')

DDL = [
    ("""CREATE TABLE IF NOT EXISTS pool_annotation (
            id            SERIAL PRIMARY KEY,
            item_id       INTEGER NOT NULL REFERENCES pool_item(id),
            rater_id      INTEGER NOT NULL REFERENCES rater(id),
            team_id       INTEGER,
            task_id       INTEGER,
            pull_id       VARCHAR(64),
            status        VARCHAR(16) NOT NULL DEFAULT 'claimed',
            final_text    TEXT,
            final_difficulty VARCHAR(32),
            is_edited     BOOLEAN NOT NULL DEFAULT FALSE,
            is_flagged    BOOLEAN NOT NULL DEFAULT FALSE,
            flag_reason   VARCHAR(255),
            notes         TEXT,
            results_json  JSON,
            claimed_at    TIMESTAMP,
            completed_at  TIMESTAMP,
            time_taken_ms INTEGER,
            revision      INTEGER NOT NULL DEFAULT 0
        )""", 'create pool_annotation'),
    # One annotation per person per prompt: a second pull by the same annotator
    # cannot create a duplicate, and an edit updates the row they already have.
    ("""CREATE UNIQUE INDEX IF NOT EXISTS uq_pool_annotation_item_rater
            ON pool_annotation(item_id, rater_id)""", 'unique (item, rater)'),
    ("""CREATE INDEX IF NOT EXISTS ix_pool_annotation_item
            ON pool_annotation(item_id)""", 'index on item'),
    ("""CREATE INDEX IF NOT EXISTS ix_pool_annotation_rater
            ON pool_annotation(rater_id, status)""", 'index on rater+status'),
    ("""CREATE INDEX IF NOT EXISTS ix_pool_annotation_pull
            ON pool_annotation(pull_id)""", 'index on pull'),
    ("""CREATE INDEX IF NOT EXISTS ix_pool_annotation_task
            ON pool_annotation(task_id, status)""", 'index on task+status'),
]

BACKFILL = """
INSERT INTO pool_annotation (
    item_id, rater_id, team_id, task_id, pull_id, status, final_text,
    final_difficulty, is_edited, is_flagged, flag_reason, notes, results_json,
    claimed_at, completed_at, time_taken_ms, revision)
SELECT i.id,
       COALESCE(i.completed_by, i.claimed_by),
       i.team_id, i.task_id, i.pull_id,
       CASE WHEN i.status IN ('completed', 'flagged') THEN i.status ELSE 'claimed' END,
       i.final_text, i.final_difficulty,
       COALESCE(i.is_edited, FALSE), COALESCE(i.is_flagged, FALSE),
       i.flag_reason, i.notes,
       CASE WHEN json_typeof(i.extra_json) = 'object'
            THEN i.extra_json -> 'results' ELSE NULL END,
       i.claimed_at, i.completed_at, i.time_taken_ms, COALESCE(i.revision, 0)
  FROM pool_item i
 WHERE COALESCE(i.completed_by, i.claimed_by) IS NOT NULL
   AND NOT EXISTS (SELECT 1 FROM pool_annotation a
                    WHERE a.item_id = i.id
                      AND a.rater_id = COALESCE(i.completed_by, i.claimed_by))
"""


def uri():
    with open(os.path.join(BACKEND_DIR, '.env'), encoding='utf-8') as f:
        for line in f:
            if line.startswith('DATABASE_URI'):
                return line.split('=', 1)[1].strip().strip('"').strip("'")
    sys.exit('DATABASE_URI not found')


def main():
    dry = '--dry-run' in sys.argv
    eng = sa.create_engine(uri())

    with eng.connect() as c:
        exists = c.execute(sa.text(
            "SELECT to_regclass('public.pool_annotation') IS NOT NULL")).scalar()
        print(f'pool_annotation exists: {exists}')
        todo = c.execute(sa.text("""
            SELECT count(*) FROM pool_item
             WHERE COALESCE(completed_by, claimed_by) IS NOT NULL""")).scalar()
        print(f'items with an inline annotation to carry over: {todo:,}')

    if dry:
        print('\n--dry-run: nothing written.')
        return 0

    # AUTOCOMMIT: each DDL is its own transaction, so one that cannot get its
    # lock fails alone instead of rolling the rest back.
    with eng.connect().execution_options(isolation_level='AUTOCOMMIT') as c:
        c.execute(sa.text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
        for stmt, label in DDL:
            try:
                c.execute(sa.text(stmt))
                print(f'  ok: {label}')
            except Exception as e:
                print(f'  FAILED ({label}): {str(e).splitlines()[0]}')
                print('  nothing else attempted; the app was not blocked.')
                return 1

    with eng.begin() as c:
        c.execute(sa.text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
        n = c.execute(sa.text(BACKFILL)).rowcount
        print(f'\nbackfilled {n:,} annotation(s) from pool_item')

    with eng.connect() as c:
        total = c.execute(sa.text('SELECT count(*) FROM pool_annotation')).scalar()
        by_status = c.execute(sa.text(
            'SELECT status, count(*) FROM pool_annotation GROUP BY 1 ORDER BY 2 DESC')).all()
        print(f'pool_annotation now holds {total:,} row(s)')
        for st, n in by_status:
            print(f'   {st:<10} {n:,}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
