import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv
from flask_cors import CORS
from sqlalchemy import event
from sqlalchemy.engine import Engine
from application.database import db
from application.models import *

# Load environment variables
load_dotenv()


# SQLite performance/concurrency pragmas. (No-op for PostgreSQL: PRAGMA would poison a psycopg2 connection, so bail out unless this really is SQLite.)
@event.listens_for(Engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    import sqlite3 as _sqlite3
    if not isinstance(dbapi_connection, _sqlite3.Connection):
        return
    try:
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA synchronous=NORMAL")
        cur.execute("PRAGMA busy_timeout=30000")   # wait up to 30s for a lock
        cur.execute("PRAGMA cache_size=-65536")    # ~64MB page cache per connection
        cur.execute("PRAGMA temp_store=MEMORY")
        cur.execute("PRAGMA foreign_keys=ON")
        # Memory-map the DB file so page reads come from the OS page cache instead of a read() syscall per page.
        cur.execute("PRAGMA mmap_size=2147483648")
        # Keep the -wal file from growing without bound (it had reached 57MB, which slows every reader down); checkpoint it once it passes ~8MB.
        cur.execute("PRAGMA wal_autocheckpoint=2000")
        cur.close()
    except Exception:
        # Non-SQLite engines (or a locked DB during startup) must not crash boot.
        pass

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/api/static')
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=300)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
    # Connection pool. The connect_args differ per engine: SQLite wants its file-lock timeout and thread flag; PostgreSQL wants a network connect timeout. Sync workers serve one request at a time, so a small pool per worker is plenty.
    uri = os.getenv('DATABASE_URI') or ''
    if uri.startswith('sqlite'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 1800,
            'connect_args': {'timeout': 30, 'check_same_thread': False},
        }
    else:
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            'pool_pre_ping': True,
            'pool_recycle': 1800,
            'pool_size': 2,
            'max_overflow': 3,
            'connect_args': {'connect_timeout': 10},
        }
    app.app_context().push()

    # Initialize database
    db.init_app(app)
    app.app_context().push()
    return app

app = create_app()

# Schema work happens ONCE per deploy (the start script runs it before gunicorn).
# Workers must NOT repeat it: on PostgreSQL every ALTER TABLE takes an ACCESS
# EXCLUSIVE lock, and a recycling worker re-running these would stall the whole
# app behind that lock queue every few hundred requests.
_RUN_BOOT_MIGRATIONS = os.getenv('SAFFRON_SKIP_BOOT_MIGRATIONS') != '1'

with app.app_context():
  if _RUN_BOOT_MIGRATIONS:
    db.create_all()
    # Self-healing migration to add completion_status column to rating table
    try:
        # PostgreSQL syntax first
        db.session.execute(db.text("ALTER TABLE rating ADD COLUMN IF NOT EXISTS completion_status VARCHAR(50) DEFAULT 'completed'"))
        db.session.commit()
        print("Database migration: Successfully verified/added completion_status column (PostgreSQL)")
    except Exception as e:
        db.session.rollback()
        try:
            # SQLite / Standard fallback
            db.session.execute(db.text("ALTER TABLE rating ADD COLUMN completion_status VARCHAR(50) DEFAULT 'completed'"))
            db.session.commit()
            print("Database migration: Successfully added completion_status column (SQLite)")
        except Exception as ex:
            db.session.rollback()
            # Ignore error if it means the column already exists
            print("Database migration info: Column 'completion_status' may already exist.")

    # Self-healing migration to add assigned_tasks column to rater table
    try:
        # PostgreSQL syntax first
        db.session.execute(db.text("ALTER TABLE rater ADD COLUMN IF NOT EXISTS assigned_tasks VARCHAR(1024) DEFAULT ''"))
        db.session.commit()
        print("Database migration: Successfully verified/added assigned_tasks column (PostgreSQL)")
    except Exception as e:
        db.session.rollback()
        try:
            # SQLite / Standard fallback
            db.session.execute(db.text("ALTER TABLE rater ADD COLUMN assigned_tasks VARCHAR(1024) DEFAULT ''"))
            db.session.commit()
            print("Database migration: Successfully added assigned_tasks column (SQLite)")
        except Exception as ex:
            db.session.rollback()
            # Ignore error if it means the column already exists
            print("Database migration info: Column 'assigned_tasks' may already exist.")

    # Self-healing migrations for admin deactivation (reversible account state).
    for col_ddl_pg, col_ddl_lite, col_name in [
        ("ALTER TABLE rater ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE",
         "ALTER TABLE rater ADD COLUMN is_active BOOLEAN DEFAULT 1", "is_active"),
        ("ALTER TABLE rater ADD COLUMN IF NOT EXISTS prev_assigned_tasks VARCHAR(1024) DEFAULT ''",
         "ALTER TABLE rater ADD COLUMN prev_assigned_tasks VARCHAR(1024) DEFAULT ''", "prev_assigned_tasks"),
    ]:
        try:
            db.session.execute(db.text(col_ddl_pg))
            db.session.commit()
            print(f"Database migration: Successfully verified/added {col_name} column (PostgreSQL)")
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text(col_ddl_lite))
                db.session.commit()
                print(f"Database migration: Successfully added {col_name} column (SQLite)")
            except Exception:
                db.session.rollback()
                print(f"Database migration info: Column '{col_name}' may already exist.")

    # Self-healing migrations for admin message view/edit (broadcast grouping + edit timestamp).
    for col_ddl_pg, col_ddl_lite, col_name in [
        ("ALTER TABLE message ADD COLUMN IF NOT EXISTS broadcast_id VARCHAR(64)",
         "ALTER TABLE message ADD COLUMN broadcast_id VARCHAR(64)", "broadcast_id"),
        ("ALTER TABLE message ADD COLUMN IF NOT EXISTS edited_at TIMESTAMP",
         "ALTER TABLE message ADD COLUMN edited_at DATETIME", "edited_at"),
    ]:
        try:
            db.session.execute(db.text(col_ddl_pg))
            db.session.commit()
            print(f"Database migration: Successfully verified/added {col_name} column (PostgreSQL)")
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text(col_ddl_lite))
                db.session.commit()
                print(f"Database migration: Successfully added {col_name} column (SQLite)")
            except Exception:
                db.session.rollback()
                print(f"Database migration info: Column '{col_name}' may already exist.")

    # Self-healing migration for per-task handoff mode (admin toggle). Additive only.
    for col_ddl_pg, col_ddl_lite, col_name in [
        ("ALTER TABLE test ADD COLUMN IF NOT EXISTS handoff_mode BOOLEAN DEFAULT FALSE",
         "ALTER TABLE test ADD COLUMN handoff_mode BOOLEAN DEFAULT 0", "handoff_mode"),
    ]:
        try:
            db.session.execute(db.text(col_ddl_pg))
            db.session.commit()
            print(f"Database migration: Successfully verified/added {col_name} column (PostgreSQL)")
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text(col_ddl_lite))
                db.session.commit()
                print(f"Database migration: Successfully added {col_name} column (SQLite)")
            except Exception:
                db.session.rollback()
                print(f"Database migration info: Column '{col_name}' may already exist.")

    # One-time backfill: broadcasts sent before broadcast_id existed have one row per annotator with no grouping id.
    try:
        import uuid as _uuid
        legacy = Message.query.filter(
            Message.category == 'broadcast', Message.broadcast_id.is_(None)
        ).all()
        if legacy:
            groups = {}
            for m in legacy:
                key = (m.body, m.created_at.replace(microsecond=0) if m.created_at else None)
                groups.setdefault(key, []).append(m)
            for rows in groups.values():
                bid = _uuid.uuid4().hex
                for m in rows:
                    m.broadcast_id = bid
            db.session.commit()
            print(f"Database migration: backfilled broadcast_id for {len(legacy)} legacy broadcast row(s) "
                  f"in {len(groups)} group(s)")
    except Exception as e:
        db.session.rollback()
        print(f"Database migration info: broadcast_id backfill skipped ({e})")

    # Multi-team (Bodhan.AI) schema: teams, memberships, team-scoped admin logins, the pull-based task pool, and the guarded drop of the empty Prolific tables.
    try:
        from application.migrations import run_migrations
        run_migrations()
    except Exception as e:
        db.session.rollback()
        print(f"Database migration ERROR (multi-team): {e}")

# Routes
from application.views import *

# App Initialization
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4020, debug=False)
