"""Schema/bootstrap migrations for the multi-team (Bodhan.AI) platform."""

import os
from datetime import datetime

from sqlalchemy import inspect, text

from application.models import (
    db, Team, TeamMember, AdminUser, PoolItem, PoolTask, Test, Rater,
)

# The organisation the platform belongs to, and the teams it ships with.
ORG_NAME = os.getenv('ORG_NAME', 'Bodhan.AI')

DEFAULT_TEAMS = [
    dict(key='tts', name='TTS Team', workflow='classic', accent='#4f46e5',
         description='Text-to-speech data: conversations, sentences, benchmarks and audio segmentation.'),
    dict(key='asr', name='ASR Team', workflow='pool', accent='#0d9488',
         description='Speech recognition prompt curation: text review and difficulty labelling.'),
]

# Tables from the retired Prolific recruitment flow. Dropped ONLY when empty.
RETIRED_TABLES = ['consent', 'session', 'study']

POOL_INDEXES = [
    ("ix_pool_item_team_status_lang", "pool_item(team_id, status, language)"),
    ("ix_pool_item_claimed_by", "pool_item(claimed_by, status)"),
    ("ix_pool_item_completed_by", "pool_item(completed_by)"),
    ("ix_pool_item_lang_class", "pool_item(language, class_label)"),
    ("ix_pool_item_pull", "pool_item(pull_id)"),
    ("ix_pool_item_upload", "pool_item(upload_id)"),
    # Task-level work: every dashboard number and every pull is scoped by task.
    ("ix_pool_item_task_status", "pool_item(task_id, status)"),
    ("ix_pool_item_task_cat_status", "pool_item(task_id, category, status)"),
    ("ix_pool_task_assignment_rater", "pool_task_assignment(rater_id, is_active)"),
    ("ix_pool_pull_rater", "pool_pull(rater_id, status)"),
    ("ix_team_member_rater", "team_member(rater_id)"),
    ("ix_test_team", "test(team_id)"),
]

# One task, one annotator: a second ACTIVE assignment of the same task cannot be written at all, so two annotators can never be pulling from the same task. (The WHERE clause differs per dialect: SQLite stores booleans as 0/1, PostgreSQL as true booleans.)
def _unique_indexes():
    active = "is_active = 1" if db.engine.dialect.name == 'sqlite' else "is_active"
    return [
        ("uq_pool_task_active_assignee", f"pool_task_assignment(task_id) WHERE {active}"),
    ]


def _log(msg):
    print(f"[migrate] {msg}", flush=True)


def _has_column(table, column):
    try:
        return column in {c['name'] for c in inspect(db.engine).get_columns(table)}
    except Exception:
        return False


def _table_exists(table):
    try:
        return table in inspect(db.engine).get_table_names()
    except Exception:
        return False


def _add_column(table, column, ddl_type, default_sql=None):
    """Additive ALTER TABLE, tolerant of the column already being there."""
    if _has_column(table, column):
        return False
    default = f" DEFAULT {default_sql}" if default_sql is not None else ""
    try:
        db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}{default}"))
        db.session.commit()
        _log(f"added column {table}.{column}")
        return True
    except Exception as e:
        db.session.rollback()
        _log(f"column {table}.{column} not added ({e})")
        return False


def _ensure_index(name, target, unique=False):
    kind = "UNIQUE INDEX" if unique else "INDEX"
    try:
        db.session.execute(text(f"CREATE {kind} IF NOT EXISTS {name} ON {target}"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _log(f"index {name} skipped ({e})")


def _drop_if_empty(table):
    """Drop a table ONLY if it exists and holds zero rows."""
    if not _table_exists(table):
        return
    try:
        n = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
    except Exception as e:
        db.session.rollback()
        _log(f"could not count {table}, leaving it alone ({e})")
        return
    if n:
        _log(f"KEEPING table '{table}': it holds {n} row(s) -- refusing to drop data")
        return
    try:
        db.session.execute(text(f"DROP TABLE {table}"))
        db.session.commit()
        _log(f"dropped empty legacy table '{table}'")
    except Exception as e:
        db.session.rollback()
        _log(f"drop of '{table}' skipped ({e})")


def _upgrade_pool_task_unique():
    """Widen pool_task's unique constraint from (team, language, class) to (team, language, class, task_type), so a second kind of work over the same slice forms its own task. SQLite cannot alter a constraint in place, so the table is rebuilt once; every later boot sees the new constraint and returns immediately. On other engines the schema comes from create_all(), which already includes task_type."""
    import re

    if db.engine.dialect.name != 'sqlite' or not _table_exists('pool_task'):
        return
    ddl = db.session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='pool_task'"
    )).scalar() or ''
    m = re.search(r'UNIQUE\s*\(([^)]*)\)', ddl, re.I)
    if m is None or 'task_type' in m.group(1):
        return

    index_ddls = [row[0] for row in db.session.execute(text(
        "SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='pool_task' "
        "AND sql IS NOT NULL")).all()]
    db.session.commit()   # release the session's transaction before raw DDL

    new_ddl = (ddl[:m.start(1)] + m.group(1).rstrip() + ', task_type' + ddl[m.end(1):])
    new_ddl = re.sub(r'CREATE TABLE\s+"?pool_task"?', 'CREATE TABLE pool_task_new',
                     new_ddl, count=1, flags=re.I)

    conn = db.engine.connect().execution_options(isolation_level='AUTOCOMMIT')
    try:
        cols = [row[1] for row in conn.exec_driver_sql(
            "PRAGMA table_info(pool_task)").fetchall()]
        col_list = ', '.join(cols)
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        conn.exec_driver_sql(new_ddl)
        conn.exec_driver_sql(
            f"INSERT INTO pool_task_new ({col_list}) SELECT {col_list} FROM pool_task")
        conn.exec_driver_sql("DROP TABLE pool_task")
        conn.exec_driver_sql("ALTER TABLE pool_task_new RENAME TO pool_task")
        for idx in index_ddls:
            conn.exec_driver_sql(idx)
        conn.exec_driver_sql("COMMIT")
        _log("rebuilt pool_task: unique constraint now includes task_type")
    except Exception as e:
        try:
            conn.exec_driver_sql("ROLLBACK")
        except Exception:
            pass
        _log(f"pool_task unique-constraint upgrade skipped ({e})")
    finally:
        try:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        finally:
            conn.close()


def seed_teams():
    created = []
    for spec in DEFAULT_TEAMS:
        team = Team.query.filter_by(key=spec['key']).first()
        if team is None:
            team = Team(**spec)
            db.session.add(team)
            created.append(spec['key'])
    if created:
        db.session.commit()
        _log(f"seeded teams: {', '.join(created)}")
    return {t.key: t for t in Team.query.all()}


def seed_admins(teams):
    """Organisation admin + one admin per team."""
    from werkzeug.security import generate_password_hash

    specs = [
        dict(username='admin', team=None, display_name=f'{ORG_NAME} Admin',
             password=os.getenv('ADMIN_PASSWORD', 'admin')),
        dict(username='tts-admin', team='tts', display_name='TTS Team Admin',
             password=os.getenv('TTS_ADMIN_PASSWORD') or os.getenv('ADMIN_PASSWORD', 'admin')),
        dict(username='asr-admin', team='asr', display_name='ASR Team Admin',
             password=os.getenv('ASR_ADMIN_PASSWORD') or os.getenv('ADMIN_PASSWORD', 'admin')),
    ]
    created = []
    for spec in specs:
        if AdminUser.query.filter_by(username=spec['username']).first():
            continue
        team = teams.get(spec['team']) if spec['team'] else None
        db.session.add(AdminUser(
            username=spec['username'],
            password=generate_password_hash(spec['password']),
            display_name=spec['display_name'],
            team_id=team.id if team else None,
        ))
        created.append(spec['username'])
    if created:
        db.session.commit()
        _log(f"seeded admin logins: {', '.join(created)}")


def backfill_tts_ownership(teams):
    """Every batch and every annotator that existed before teams belonged to the TTS project -- point them at the TTS team."""
    tts = teams.get('tts')
    if tts is None:
        return

    n = db.session.execute(
        text("UPDATE test SET team_id = :tid WHERE team_id IS NULL"), {'tid': tts.id}
    ).rowcount
    db.session.commit()
    if n:
        _log(f"backfilled team_id=tts on {n} existing batch(es)")

    # One TeamMember row per pre-existing annotator, TTS team.
    existing = {m.rater_id for m in TeamMember.query.filter_by(team_id=tts.id).all()}
    added = 0
    for rater in Rater.query.all():
        if rater.id in existing:
            continue
        # Membership means "belongs to this team"; whether the ACCOUNT is switched off is Rater.is_active and is handled separately (the dashboard has its own "show.
        db.session.add(TeamMember(team_id=tts.id, rater_id=rater.id, role='annotator'))
        added += 1
    if added:
        db.session.commit()
        _log(f"added {added} existing annotator(s) to the TTS team")


def backfill_denormalised():
    """Fill test.item_count / test.language_hint / rating.verdict where they are still NULL. Runs on every boot but only touches rows that have never been computed. The JSON functions differ per dialect, so each statement comes in a SQLite and a PostgreSQL form."""
    pg = db.engine.dialect.name == 'postgresql'

    item_count_sql = (
        "UPDATE test SET item_count = json_array_length(json_entry) "
        " WHERE item_count IS NULL AND json_typeof(json_entry) = 'array'" if pg else
        "UPDATE test SET item_count = json_array_length(json_entry) "
        " WHERE item_count IS NULL AND json_valid(json_entry)")
    try:
        n = db.session.execute(db.text(item_count_sql)).rowcount
        db.session.commit()
        if n:
            _log(f"backfilled item_count on {n} batch(es)")
    except Exception as e:
        db.session.rollback()
        _log(f"item_count backfill skipped ({e})")

    language_hint_sql = (
        "UPDATE test SET language_hint = COALESCE("
        "        json_entry->0->>'target_language',"
        "        json_entry->0->>'language',"
        "        json_entry->0->'metadata'->>'language', '')"
        " WHERE language_hint IS NULL AND json_typeof(json_entry) = 'array'" if pg else
        "UPDATE test SET language_hint = COALESCE("
        "        json_extract(json_entry, '$[0].target_language'),"
        "        json_extract(json_entry, '$[0].language'),"
        "        json_extract(json_entry, '$[0].metadata.language'), '')"
        " WHERE language_hint IS NULL AND json_valid(json_entry)")
    try:
        n = db.session.execute(db.text(language_hint_sql)).rowcount
        db.session.commit()
        if n:
            _log(f"backfilled language_hint on {n} batch(es)")
    except Exception as e:
        db.session.rollback()
        _log(f"language_hint backfill skipped ({e})")

    try:
        n = db.session.execute(db.text(
            "UPDATE pool_item SET task_type = 'text-review' "
            " WHERE task_type IS NULL OR task_type = ''")).rowcount
        db.session.commit()
        if n:
            _log(f"backfilled task_type on {n} pool item(s)")
    except Exception as e:
        db.session.rollback()
        _log(f"task_type backfill skipped ({e})")

    verdict_sql = (
        "UPDATE rating SET verdict = COALESCE("
        "        LOWER(TRIM(results_json->>'evaluation')),"
        "        LOWER(TRIM(results_json->>'decision')), '')"
        " WHERE id IN (SELECT id FROM rating WHERE verdict IS NULL LIMIT 20000)" if pg else
        "UPDATE rating SET verdict = COALESCE("
        "        LOWER(TRIM(json_extract(results_json, '$.evaluation'))),"
        "        LOWER(TRIM(json_extract(results_json, '$.decision'))), '')"
        " WHERE id IN (SELECT id FROM rating WHERE verdict IS NULL LIMIT 20000)")
    try:
        # Chunked so one statement never holds the write lock for long while annotators are submitting.
        total = 0
        while True:
            n = db.session.execute(db.text(verdict_sql)).rowcount
            db.session.commit()
            total += n
            if not n:
                break
        if total:
            _log(f"backfilled verdict on {total} rating(s)")
    except Exception as e:
        db.session.rollback()
        _log(f"verdict backfill skipped ({e})")


def sync_pool_tasks():
    """Make sure every (language, class, task_type) present in a pool has a PoolTask row, every pool item points at its task, and item_count is current."""
    if not _table_exists('pool_task') or not _has_column('pool_item', 'task_id'):
        return

    pool_teams = Team.query.filter_by(workflow='pool').all()
    created = 0
    for team in pool_teams:
        combos = db.session.query(
            PoolItem.language, PoolItem.class_label,
            db.func.coalesce(PoolItem.task_type, 'text-review'),
        ).filter(PoolItem.team_id == team.id).distinct().all()
        known = {(t.language, t.class_label, t.task_type or 'text-review'): t
                 for t in PoolTask.query.filter_by(team_id=team.id).all()}
        for language, class_label, task_type in combos:
            if (language, class_label, task_type) in known:
                continue
            db.session.add(PoolTask(team_id=team.id, language=language,
                                    class_label=class_label, task_type=task_type))
            created += 1
    if created:
        db.session.commit()
        _log(f"created {created} pool task(s) from the items already in the pool")

    # Point items at the task of their own (language, class, kind of work). NULL-safe class comparison: SQLite spells it IS, PostgreSQL IS NOT DISTINCT FROM.
    null_safe_eq = ('IS NOT DISTINCT FROM' if db.engine.dialect.name == 'postgresql'
                    else 'IS')
    try:
        linked = db.session.execute(text(f"""
            UPDATE pool_item
               SET task_id = (SELECT t.id FROM pool_task t
                               WHERE t.team_id = pool_item.team_id
                                 AND t.language = pool_item.language
                                 AND (t.class_label {null_safe_eq} pool_item.class_label)
                                 AND COALESCE(t.task_type, 'text-review')
                                     = COALESCE(pool_item.task_type, 'text-review'))
             WHERE task_id IS NULL
        """)).rowcount
        db.session.commit()
        if linked:
            _log(f"linked {linked} pool item(s) to their task")
    except Exception as e:
        db.session.rollback()
        _log(f"task_id backfill skipped ({e})")

    # Refresh the denormalised size of each task (cheap: one grouped scan).
    try:
        db.session.execute(text("""
            UPDATE pool_task
               SET item_count = COALESCE((SELECT COUNT(*) FROM pool_item i
                                           WHERE i.task_id = pool_task.id), 0)
        """))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        _log(f"task item_count refresh skipped ({e})")


def run_migrations():
    """Entry point called from main.py inside an app context."""
    # 1. New tables (team, team_member, admin_user, pool_upload, pool_item).
    db.create_all()

    # 2. Additive columns on pre-existing tables.
    _add_column('test', 'team_id', 'INTEGER')

    # 2b.
    _add_column('test', 'item_count', 'INTEGER')
    _add_column('test', 'language_hint', 'VARCHAR(64)')
    _add_column('rating', 'verdict', 'VARCHAR(16)')
    _add_column('pool_item', 'task_type', "VARCHAR(64) DEFAULT 'text-review'")
    _add_column('pool_item', 'task_id', 'INTEGER')
    _add_column('pool_task', 'task_type', "VARCHAR(64) NOT NULL DEFAULT 'text-review'")
    _upgrade_pool_task_unique()
    backfill_denormalised()

    # 3. Indexes for the pool workflow and team scoping.
    for name, target in POOL_INDEXES:
        _ensure_index(name, target)
    for name, target in _unique_indexes():
        _ensure_index(name, target, unique=True)

    # 4. Seed the organisation's teams + admin logins, then backfill ownership.
    teams = seed_teams()
    seed_admins(teams)
    backfill_tts_ownership(teams)

    # 4b.
    sync_pool_tasks()

    # 5. Retire the empty Prolific-era tables (guarded: empty tables only).
    for table in RETIRED_TABLES:
        _drop_if_empty(table)

    _log("multi-team migrations complete")
