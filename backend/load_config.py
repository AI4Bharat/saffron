import json
import argparse, os, random
from enum import Enum
from application.database import db
from application.models import Test, Study
from main import app

class TestType(Enum):
    HFR = "hfr"
    MUSHRA_GRANULAR = "mushra-granular"
    MUSHRA = "mushra"
    MVH_GRANULAR = "hfr-granular"
    CMOS = "cmos"

def load_json_config(config_path: str):
    with open(config_path, 'r') as f:
        return json.load(f)
    
def populate_database_from_config(test_type: TestType, config_data: list, prolific=False, description=""):
    with app.app_context():
        if description:
            description = description
        else:
            description = f"Test data from config for {test_type.value} task"
        test = Test(
            id=db.session.query(db.func.max(Test.id)).scalar() + 1 if db.session.query(db.func.max(Test.id)).scalar() is not None else 1,
            test_type=test_type,
            description=description,
            json_entry=config_data
        )
        db.session.add(test)
        db.session.commit()

        if prolific:
            study_id=f"123456"
            study = Study(
                id=db.session.query(db.func.max(Study.id)).scalar() + 1 if db.session.query(db.func.max(Study.id)).scalar() is not None else 1,
                test_id=test.id,
                study_id=study_id,
                completion_url=f"https://app.prolific.co/submissions/complete?cc=12345678"
            )
            print(f"Study ID: {study_id}")
            db.session.add(study)
            db.session.commit()

        print(f"test id for {description}", test.id)
        # print(f"Database populated successfully with {test_type} test data from config!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Load test data from config file')
    parser.add_argument('config_path', help='Path to the JSON config file')
    parser.add_argument('--test-type', required=True, 
                      choices=[t.value for t in TestType],
                      help='Type of test to create')
    parser.add_argument('--prolific', action='store_true',
                      help='Create Prolific study')
    
    args = parser.parse_args()
    
    config_data = load_json_config(args.config_path)
    test_type = next(t for t in TestType if t.value == args.test_type)
    
    populate_database_from_config(test_type, config_data, args.prolific)

# Example usage:
# python load_config.py path/to/config.json --test-type "HFR" --prolific