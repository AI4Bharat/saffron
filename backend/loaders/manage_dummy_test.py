import os
import sys
import json
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test, Rating, Consent

def create_dummy_test():
    dummy_json = [
        {
            "id": 99991,
            "slug": "dummy_task_1",
            "description": "Dummy Dialogue 1 (Simple)",
            "target_language": "hindi",
            "pre_scene": "शिक्षक कक्षा में प्रवेश करता है।",
            "pre_scene_en": "The teacher enters the classroom.",
            "conversation": [
                {
                    "speaker": "Teacher",
                    "english": "Hello everyone, today we will learn fractions.",
                    "translation": "नमस्ते सभी को, आज हम अंशों को सीखेंगे।",
                    "role": "teacher"
                },
                {
                    "speaker": "Student",
                    "english": "Sir, is it difficult?",
                    "translation": "सर, क्या यह कठिन है?",
                    "role": "student"
                }
            ],
            "post_scene": "छात्र ध्यान से सुनते हैं।",
            "post_scene_en": "The students listen carefully."
        },
        {
            "id": 99992,
            "slug": "dummy_task_2",
            "description": "Dummy Dialogue 2 (Simple)",
            "target_language": "hindi",
            "pre_scene": "शिक्षक ब्लैकबोर्ड पर लिखता है।",
            "pre_scene_en": "The teacher writes on the blackboard.",
            "conversation": [
                {
                    "speaker": "Teacher",
                    "english": "Look at this circle.",
                    "translation": "इस वृत्त को देखो।",
                    "role": "teacher"
                },
                {
                    "speaker": "Student",
                    "english": "Yes, sir.",
                    "translation": "हाँ, सर।",
                    "role": "student"
                }
            ],
            "post_scene": "शिक्षक पढ़ाना जारी रखता है।",
            "post_scene_en": "The teacher continues teaching."
        }
    ]

    with app.app_context():
        # Check if already exists
        existing = Test.query.get(9999)
        if existing:
            print("Test with ID 9999 already exists.")
            return

        test = Test(
            id=9999,
            test_type="translation-correction",
            description="Dummy Translation Correction Test Batch (ID: 9999)",
            json_entry=dummy_json
        )
        db.session.add(test)
        db.session.commit()
        print("Successfully created dummy translation-correction test with ID 9999.")
        print("You can view it in the app by going to task: /9999")

def delete_dummy_test():
    with app.app_context():
        # Delete related consents
        Consent.query.filter_by(test_id=9999).delete()
        # Delete related ratings
        Rating.query.filter_by(test_id=9999).delete()
        # Delete test itself
        Test.query.filter_by(id=9999).delete()
        db.session.commit()
        print("Successfully deleted dummy test 9999 and all associated ratings/consents.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Manage dummy test for translation correction validation")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--create", action="store_true", help="Create the dummy test")
    group.add_argument("--delete", action="store_true", help="Delete the dummy test and all ratings")
    
    args = parser.parse_args()
    if args.create:
        create_dummy_test()
    elif args.delete:
        delete_dummy_test()
