import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from threading import Lock
from dotenv import load_dotenv
from flask_cors import CORS
from application.database import db
from application.models import *

# Load environment variables
load_dotenv()

def create_app():
    app = Flask(__name__, static_folder='static', static_url_path='/api/static')
    CORS(app, resources={r"/*": {"origins": "*"}})
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=300)
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB
    app.app_context().push()

    # Initialize database
    db.init_app(app)
    app.app_context().push()
    return app

app = create_app()
with app.app_context():
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
    # Additive only — no existing rows/data are modified by these ALTERs.
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

    # Self-healing migrations for admin message view/edit (broadcast grouping +
    # edit timestamp). Additive only — no existing rows/data are modified here.
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

    # One-time backfill: broadcasts sent before broadcast_id existed have one row
    # per annotator with no grouping id. Group the legacy rows by (body, second)
    # and give each group a shared id so the admin can view/edit them as one
    # broadcast. Idempotent — only touches rows whose broadcast_id is still NULL.
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

# Routes
from application.views import *

# App Initialization
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4020, debug=False)
