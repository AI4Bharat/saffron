import os
import sys

# Add backend directory to path to ensure relative imports function correctly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test, Study, Session, Rating, Consent

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# ENTER THE TASK ID (Test ID) OR A LIST OF TASK IDS YOU WANT TO DELETE HERE:
# 
# Examples:
#   For a single task:    TASK_IDS = [1]
#   For multiple tasks:   TASK_IDS = [1, 2, 3]
# 
# Leave it empty to prevent any action.
TASK_IDS = [i for i in range(20091,20098)]

# DRY RUN MODE (Safe Mode):
# If True, the script will only scan and list what records would be deleted.
# Set this to False when you are ready to perform the actual deletion.
DRY_RUN = False
# ==============================================================================

def delete_tasks(task_ids, dry_run=True):
    if not task_ids:
        print("No Task IDs specified in the TASK_IDS variable. Please populate it in the script.")
        return

    # Ensure task_ids is list-like
    if not isinstance(task_ids, list):
        if isinstance(task_ids, (int, str)):
            task_ids = [task_ids]
        else:
            task_ids = list(task_ids)

    # Convert elements to integers if possible
    normalized_task_ids = []
    for tid in task_ids:
        try:
            normalized_task_ids.append(int(tid))
        except (ValueError, TypeError):
            normalized_task_ids.append(tid)

    print(f"Task IDs to process: {normalized_task_ids}")
    print(f"Dry Run: {dry_run}")
    print("-" * 60)

    with app.app_context():
        try:
            # 1. Fetch the Tasks/Tests
            tasks = Test.query.filter(Test.id.in_(normalized_task_ids)).all()
            found_ids = [task.id for task in tasks]
            missing_ids = [tid for tid in normalized_task_ids if tid not in found_ids]

            if not tasks:
                print("No tasks found in the database matching the provided IDs.")
                return

            if missing_ids:
                print(f"Warning: The following Task IDs were not found in the database: {missing_ids}")

            print(f"Found {len(tasks)} task(s) to delete:")
            for task in tasks:
                print(f"  - ID: {task.id} | Type: {task.test_type} | Description: {task.description or 'N/A'}")

            # 2. Find related Study and Session records
            studies = Study.query.filter(Study.test_id.in_(found_ids)).all()
            study_ids = [s.id for s in studies]

            sessions = []
            if study_ids:
                sessions = Session.query.filter(Session.study_id.in_(study_ids)).all()

            # 3. Find related Rating and Consent records
            ratings = Rating.query.filter(Rating.test_id.in_(found_ids)).all()
            consents = Consent.query.filter(Consent.test_id.in_(found_ids)).all()

            # 4. Print summary of associated records that will be deleted
            print("-" * 60)
            print("Associated records found:")
            print(f"  - Sessions to delete: {len(sessions)}")
            print(f"  - Studies to delete:  {len(studies)}")
            print(f"  - Ratings to delete:  {len(ratings)}")
            print(f"  - Consents to delete: {len(consents)}")
            print("-" * 60)

            if dry_run:
                print("DRY RUN MODE: No database changes were made.")
                print("To execute the deletion, set DRY_RUN = False and specify task IDs in the script.")
                return

            # 5. Delete records in correct order to satisfy Foreign Key constraints
            # Step A: Delete Sessions (references Study)
            if sessions:
                print(f"Deleting {len(sessions)} associated session(s)...")
                for session in sessions:
                    db.session.delete(session)

            # Step B: Delete Studies (references Test)
            if studies:
                print(f"Deleting {len(studies)} associated study(ies)...")
                for study in studies:
                    db.session.delete(study)

            # Step C: Delete Ratings (references Test)
            if ratings:
                print(f"Deleting {len(ratings)} associated rating(s)...")
                for rating in ratings:
                    db.session.delete(rating)

            # Step D: Delete Consents (references Test)
            if consents:
                print(f"Deleting {len(consents)} associated consent(s)...")
                for consent in consents:
                    db.session.delete(consent)

            # Step E: Delete Tests/Tasks themselves
            print(f"Deleting {len(tasks)} task(s)...")
            for task in tasks:
                db.session.delete(task)

            # Commit transaction
            db.session.commit()
            print("Database transaction completed and changes committed successfully!")

        except Exception as e:
            db.session.rollback()
            print(f"Error during deletion transaction: {e}")
            print("Database transaction rolled back. No changes were saved.")

if __name__ == "__main__":
    delete_tasks(TASK_IDS, dry_run=DRY_RUN)
