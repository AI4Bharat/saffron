import os
import sys
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Rater, Rating, Consent

def load_emails(file_path):
    """Loads and sanitizes emails from a text file."""
    if not os.path.exists(file_path):
        print(f"Error: Email file not found at '{file_path}'")
        return []
    
    emails = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines or comment lines
            if not line or line.startswith('#'):
                continue
            emails.append(line.lower())
    return list(set(emails))  # Return unique emails

def delete_raters(emails, commit=False, no_confirm=False):
    """Finds and deletes raters and their associated records."""
    if not emails:
        print("No emails found to process. Please populate 'emails_to_delete.txt'.")
        return

    print(f"Loaded {len(emails)} unique email(s) to process.")
    print("-" * 50)

    with app.app_context():
        # Keep track of records to delete
        raters_to_delete = []
        ratings_to_delete = []
        consents_to_delete = []
        emails_not_found = []

        for email in emails:
            rater = Rater.query.filter_by(email=email).first()
            if not rater:
                emails_not_found.append(email)
                continue
            
            # Fetch related records
            ratings = Rating.query.filter_by(rater_id=rater.id).all()
            consents = Consent.query.filter_by(rater_id=rater.id).all()
            
            raters_to_delete.append(rater)
            ratings_to_delete.extend(ratings)
            consents_to_delete.extend(consents)

        # Print summary
        if emails_not_found:
            print("Emails not found in database:")
            for email in emails_not_found:
                print(f"  - {email}")
            print("-" * 50)

        if not raters_to_delete:
            print("No matching Rater records found in the database. Nothing to delete.")
            return

        print("Records identified for deletion:")
        print(f"  Raters to delete:   {len(raters_to_delete)}")
        for r in raters_to_delete:
            print(f"    * ID: {r.id} | Name: {r.name} | Email: {r.email}")
        print(f"  Ratings to delete:  {len(ratings_to_delete)}")
        print(f"  Consents to delete: {len(consents_to_delete)}")
        print("-" * 50)

        # Handle Dry-Run Mode
        if not commit:
            print("DRY RUN MODE: No changes have been made to the database.")
            print("To execute this deletion, run the script with the --commit flag:")
            print("  python delete_raters.py --commit")
            return

        # Confirmation step
        if not no_confirm:
            confirmation = input("WARNING: This action is permanent and cannot be undone. Proceed? (yes/no): ")
            if confirmation.strip().lower() not in ['yes', 'y']:
                print("Deletion aborted by user.")
                return

        try:
            print("Starting deletion...")
            
            # 1. Delete associated ratings
            if ratings_to_delete:
                print(f"Deleting {len(ratings_to_delete)} Rating record(s)...")
                for rating in ratings_to_delete:
                    db.session.delete(rating)

            # 2. Delete associated consents
            if consents_to_delete:
                print(f"Deleting {len(consents_to_delete)} Consent record(s)...")
                for consent in consents_to_delete:
                    db.session.delete(consent)

            # 3. Delete rater records
            print(f"Deleting {len(raters_to_delete)} Rater record(s)...")
            for rater in raters_to_delete:
                db.session.delete(rater)

            # Commit the transaction
            db.session.commit()
            print("Deletion completed successfully and changes committed to the database.")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error during deletion transaction: {e}")
            print("Database transaction rolled back. No changes were applied.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Delete specific raters and their associated ratings/consents based on email address.")
    parser.add_argument("--commit", action="store_true", help="Actually execute the deletion and commit changes to the database (defaults to dry-run).")
    parser.add_argument("--no-confirm", action="store_true", help="Skip the interactive confirmation prompt (only works if --commit is also set).")
    parser.add_argument("--file", default="emails_to_delete.txt", help="Path to the file containing the list of email addresses (default: emails_to_delete.txt).")
    
    args = parser.parse_args()
    
    # Resolve relative path for the email file
    file_path = args.file
    if not os.path.isabs(file_path):
        file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), file_path))
        
    emails = load_emails(file_path)
    delete_raters(emails, commit=args.commit, no_confirm=args.no_confirm)
