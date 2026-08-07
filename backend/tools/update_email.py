import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Rater

# CONFIGURATION: Set the old and new email values below
OLD_EMAIL = "hananavaheed@test.com"
NEW_EMAIL = "hananavaheed@gmail.com"
# ==============================================================================


def update_rater_email(old_email: str, new_email: str) -> bool:
    """Updates the email address of a rater in the database."""
    old_email_clean = old_email.strip().lower() if old_email else ""
    new_email_clean = new_email.strip().lower() if new_email else ""

    if not old_email_clean or not new_email_clean:
        print("Error: Both OLD_EMAIL and NEW_EMAIL must be non-empty strings.")
        return False

    if old_email_clean == new_email_clean:
        print("OLD_EMAIL and NEW_EMAIL are the same. No update needed.")
        return True

    with app.app_context():
        # Find rater with old email
        rater = Rater.query.filter(db.func.lower(Rater.email) == old_email_clean).first()
        if not rater:
            print(f"Error: No rater found with email '{old_email}'.")
            return False

        # Check if new email is already in use
        existing_new_rater = Rater.query.filter(
            db.func.lower(Rater.email) == new_email_clean
        ).first()
        if existing_new_rater:
            print(
                f"Error: Cannot update to '{new_email}' - email already in use by Rater ID {existing_new_rater.id}."
            )
            return False

        # Perform email update
        original_email = rater.email
        rater.email = new_email_clean
        db.session.commit()

        print(
            f"Successfully updated Rater ID {rater.id} ('{rater.name}') "
            f"email from '{original_email}' to '{rater.email}'."
        )
        return True


if __name__ == "__main__":
    update_rater_email(OLD_EMAIL, NEW_EMAIL)
