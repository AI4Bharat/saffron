import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Rating, Test, Study, Session, Consent

def clear_imported_tables():
    with app.app_context():
        try:
            # Clear tables in dependency order
            db.session.query(Rating).delete()
            db.session.commit()
            print("Successfully cleared Test, Rating, Consent, Study, and Session tables.")
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing tables: {e}")

if __name__ == "__main__":
    clear_imported_tables()
