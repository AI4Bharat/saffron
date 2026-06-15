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

# Routes
from application.views import *

# App Initialization
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=4020, debug=False)
