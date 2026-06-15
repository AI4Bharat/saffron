import os
import sys
import json
import pandas as pd
from datetime import datetime

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Rater, Test, Study, Session, Rating, Consent

def serialize_json(val):
    if val is None:
        return ""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)

def backup_to_excel(output_path):
    print(f"Starting database backup using app context...")
    with app.app_context():
        # Define exact columns for each sheet to handle empty states gracefully
        RATER_COLS = ['id', 'name', 'email', 'age', 'gender', 'password']
        TEST_COLS = ['id', 'test_type', 'description']
        TEST_ITEM_COLS = ['test_id', 'item_index', 'item_json']
        STUDY_COLS = ['id', 'study_id', 'test_id', 'completion_url']
        SESSION_COLS = ['id', 'session_id', 'study_id', 'prolific_pid']
        RATING_COLS = ['id', 'rater_id', 'test_id', 'results_json', 'time_of_submission', 'time_taken_to_submit', 'page_no_progress', 'completion_status']
        CONSENT_COLS = ['id', 'rater_id', 'test_id', 'time_of_submission']

        # 1. Rater table
        raters = Rater.query.all()
        rater_data = []
        for r in raters:
            rater_data.append({
                'id': r.id,
                'name': r.name,
                'email': r.email,
                'age': r.age,
                'gender': r.gender,
                'password': r.password
            })
        df_rater = pd.DataFrame(rater_data, columns=RATER_COLS)
        print(f"Fetched {len(df_rater)} records from Rater table.")

        # 2. Test table (metadata only) and Test_Item sheet (large JSON list items split)
        tests = Test.query.all()
        test_data = []
        test_item_data = []
        for t in tests:
            test_data.append({
                'id': t.id,
                'test_type': t.test_type,
                'description': t.description
            })
            
            # Split items in json_entry list
            items = t.json_entry
            if isinstance(items, list):
                for idx, item in enumerate(items):
                    test_item_data.append({
                        'test_id': t.id,
                        'item_index': idx,
                        'item_json': json.dumps(item, ensure_ascii=False)
                    })
            elif items is not None:
                # In case it's a dict or other non-list JSON, just write as index 0
                test_item_data.append({
                    'test_id': t.id,
                    'item_index': 0,
                    'item_json': json.dumps(items, ensure_ascii=False)
                })

        df_test = pd.DataFrame(test_data, columns=TEST_COLS)
        df_test_item = pd.DataFrame(test_item_data, columns=TEST_ITEM_COLS)
        print(f"Fetched {len(df_test)} records from Test table (metadata).")
        print(f"Extracted {len(df_test_item)} individual items into Test_Item sheet.")

        # 3. Study table
        studies = Study.query.all()
        study_data = []
        for s in studies:
            study_data.append({
                'id': s.id,
                'study_id': s.study_id,
                'test_id': s.test_id,
                'completion_url': s.completion_url
            })
        df_study = pd.DataFrame(study_data, columns=STUDY_COLS)
        print(f"Fetched {len(df_study)} records from Study table.")

        # 4. Session table
        sessions = Session.query.all()
        session_data = []
        for s in sessions:
            session_data.append({
                'id': s.id,
                'session_id': s.session_id,
                'study_id': s.study_id,
                'prolific_pid': s.prolific_pid
            })
        df_session = pd.DataFrame(session_data, columns=SESSION_COLS)
        print(f"Fetched {len(df_session)} records from Session table.")

        # 5. Rating table
        ratings = Rating.query.all()
        rating_data = []
        for r in ratings:
            rating_data.append({
                'id': r.id,
                'rater_id': r.rater_id,
                'test_id': r.test_id,
                'results_json': serialize_json(r.results_json),
                'time_of_submission': r.time_of_submission.strftime('%Y-%m-%d %H:%M:%S') if r.time_of_submission else None,
                'time_taken_to_submit': r.time_taken_to_submit,
                'page_no_progress': r.page_no_progress,
                'completion_status': r.completion_status
            })
        df_rating = pd.DataFrame(rating_data, columns=RATING_COLS)
        print(f"Fetched {len(df_rating)} records from Rating table.")

        # 6. Consent table
        consents = Consent.query.all()
        consent_data = []
        for c in consents:
            consent_data.append({
                'id': c.id,
                'rater_id': c.rater_id,
                'test_id': c.test_id,
                'time_of_submission': c.time_of_submission.strftime('%Y-%m-%d %H:%M:%S') if c.time_of_submission else None
            })
        df_consent = pd.DataFrame(consent_data, columns=CONSENT_COLS)
        print(f"Fetched {len(df_consent)} records from Consent table.")

        # Ensure output directory exists
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        # Write to multi-sheet Excel file
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            df_rater.to_excel(writer, sheet_name='Rater', index=False)
            df_test.to_excel(writer, sheet_name='Test', index=False)
            df_test_item.to_excel(writer, sheet_name='Test_Item', index=False)
            df_study.to_excel(writer, sheet_name='Study', index=False)
            df_session.to_excel(writer, sheet_name='Session', index=False)
            df_rating.to_excel(writer, sheet_name='Rating', index=False)
            df_consent.to_excel(writer, sheet_name='Consent', index=False)

        print(f"Database successfully backed up to Excel: {output_path}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Backup database to a multi-sheet Excel file")
    parser.add_argument("--output", default="db_backup.xlsx", help="Output XLSX file path")
    args = parser.parse_args()
    
    # Resolve relative paths relative to the saffron root directory
    out_path = args.output
    if not os.path.isabs(out_path):
        out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", out_path))
        
    backup_to_excel(out_path)
