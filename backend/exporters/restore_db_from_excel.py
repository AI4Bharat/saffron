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

def deserialize_json(val):
    if pd.isna(val) or val == "":
        return None
    try:
        return json.loads(val)
    except Exception:
        return val

def parse_datetime(val):
    if pd.isna(val) or not val:
        return None
    if isinstance(val, datetime):
        return val
    try:
        return datetime.strptime(str(val), '%Y-%m-%d %H:%M:%S')
    except Exception:
        try:
            return pd.to_datetime(val).to_pydatetime()
        except Exception:
            return None

def restore_from_excel(input_path):
    if not os.path.exists(input_path):
        print(f"Error: Excel backup file not found at {input_path}")
        sys.exit(1)
        
    print(f"Reading backup from Excel file: {input_path}")
    
    # Read sheets
    excel_file = pd.ExcelFile(input_path)
    sheets = excel_file.sheet_names
    print(f"Found sheets: {sheets}")
    
    # Required sheets
    required = {'Rater', 'Test', 'Test_Item', 'Study', 'Session', 'Rating', 'Consent'}
    missing = required - set(sheets)
    if missing:
        print(f"Error: Missing sheets in backup file: {missing}")
        sys.exit(1)
        
    df_rater = pd.read_excel(excel_file, 'Rater')
    df_test = pd.read_excel(excel_file, 'Test')
    df_test_item = pd.read_excel(excel_file, 'Test_Item')
    df_study = pd.read_excel(excel_file, 'Study')
    df_session = pd.read_excel(excel_file, 'Session')
    df_rating = pd.read_excel(excel_file, 'Rating')
    df_consent = pd.read_excel(excel_file, 'Consent')

    with app.app_context():
        # Clear existing tables in correct dependency order
        print("Clearing current database tables in dependency order...")
        try:
            db.session.query(Session).delete()
            db.session.query(Study).delete()
            db.session.query(Consent).delete()
            db.session.query(Rating).delete()
            db.session.query(Test).delete()
            db.session.query(Rater).delete()
            db.session.commit()
            print("Successfully cleared all existing records.")
        except Exception as e:
            db.session.rollback()
            print(f"Error clearing database: {e}")
            sys.exit(1)
            
        print("Restoring database records...")
        try:
            # 1. Restore Raters
            for _, row in df_rater.iterrows():
                rater = Rater(
                    id=int(row['id']),
                    name=row['name'],
                    email=row['email'],
                    age=int(row['age']),
                    gender=row['gender'],
                    assigned_tasks=row.get('assigned_tasks') if ('assigned_tasks' in row and not pd.isna(row.get('assigned_tasks'))) else '',
                    password=row['password']
                )
                db.session.add(rater)
            db.session.flush() # Flush to database to check for constraints
            print(f"Prepared {len(df_rater)} Rater records.")

            # 2. Restore Tests (reconstruct json_entry from Test_Item)
            test_items_grouped = {}
            if len(df_test_item) > 0:
                # Group item data by test_id
                for _, row in df_test_item.iterrows():
                    test_id = int(row['test_id'])
                    idx = int(row['item_index'])
                    item_data = deserialize_json(row['item_json'])
                    
                    if test_id not in test_items_grouped:
                        test_items_grouped[test_id] = []
                    test_items_grouped[test_id].append((idx, item_data))

            for _, row in df_test.iterrows():
                test_id = int(row['id'])
                
                # Reconstruct list from sorted items
                reconstructed_list = []
                if test_id in test_items_grouped:
                    # Sort items by their original index
                    sorted_items = sorted(test_items_grouped[test_id], key=lambda x: x[0])
                    reconstructed_list = [item for _, item in sorted_items]
                    
                test = Test(
                    id=test_id,
                    test_type=row['test_type'],
                    description=row['description'] if not pd.isna(row['description']) else None,
                    json_entry=reconstructed_list
                )
                db.session.add(test)
            db.session.flush()
            print(f"Prepared {len(df_test)} Test records with reconstructed json_entries.")

            # 3. Restore Study records
            for _, row in df_study.iterrows():
                study = Study(
                    id=int(row['id']),
                    study_id=row['study_id'],
                    test_id=int(row['test_id']),
                    completion_url=row['completion_url']
                )
                db.session.add(study)
            db.session.flush()
            print(f"Prepared {len(df_study)} Study records.")

            # 4. Restore Session records
            for _, row in df_session.iterrows():
                session = Session(
                    id=int(row['id']),
                    session_id=row['session_id'],
                    study_id=int(row['study_id']),
                    prolific_pid=row['prolific_pid']
                )
                db.session.add(session)
            db.session.flush()
            print(f"Prepared {len(df_session)} Session records.")

            # 5. Restore Rating records
            for _, row in df_rating.iterrows():
                rating = Rating(
                    id=int(row['id']),
                    rater_id=int(row['rater_id']),
                    test_id=int(row['test_id']),
                    results_json=deserialize_json(row['results_json']),
                    time_of_submission=parse_datetime(row['time_of_submission']),
                    time_taken_to_submit=float(row['time_taken_to_submit']),
                    page_no_progress=str(row['page_no_progress']) if not pd.isna(row['page_no_progress']) else None,
                    completion_status=row['completion_status'] if not pd.isna(row['completion_status']) else 'completed'
                )
                db.session.add(rating)
            db.session.flush()
            print(f"Prepared {len(df_rating)} Rating records.")

            # 6. Restore Consent records
            for _, row in df_consent.iterrows():
                consent = Consent(
                    id=int(row['id']),
                    rater_id=int(row['rater_id']),
                    test_id=int(row['test_id']),
                    time_of_submission=parse_datetime(row['time_of_submission'])
                )
                db.session.add(consent)
            db.session.flush()
            print(f"Prepared {len(df_consent)} Consent records.")

            # Commit all changes to the database
            db.session.commit()
            print("Database transaction successfully committed.")

            # Sync sequence IDs if utilizing PostgreSQL
            if db.engine.dialect.name == 'postgresql':
                print("PostgreSQL database detected. Syncing primary key sequence generators...")
                for table_name in ['rater', 'test', 'study', 'session', 'rating', 'consent']:
                    db.session.execute(db.text(
                        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), COALESCE(MAX(id), 1)) FROM {table_name}"
                    ))
                db.session.commit()
                print("PostgreSQL sequences successfully synced.")

            print("Database restore completed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"Error during restore database transaction: {e}")
            sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Restore database from a multi-sheet Excel file backup")
    parser.add_argument("--input", default="db_backup.xlsx", help="Input XLSX backup file path")
    args = parser.parse_args()
    
    # Resolve relative paths relative to the saffron root directory
    in_path = args.input
    if not os.path.isabs(in_path):
        in_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", in_path))
        
    restore_from_excel(in_path)
