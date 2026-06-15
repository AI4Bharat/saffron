import json
import argparse
import os
import sys

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from load_jsonl import load_jsonl_config
from load_config import TestType

def main():
    parser = argparse.ArgumentParser(description='Split a large JSONL file into batches of 250 and load them into the database')
    parser.add_argument('config_path', help='Path to the translated JSONL config file')
    parser.add_argument('--english', help='Path to the original English JSONL config file (optional, for alignment)')
    parser.add_argument('--prolific', action='store_true', help='Create Prolific study')
    parser.add_argument('--batch-size', type=int, default=250, help='Number of tasks per batch (default: 250)')
    parser.add_argument('--description-prefix', help='Prefix for test description')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.config_path):
        print(f"Error: Config file not found at {args.config_path}")
        sys.exit(1)
        
    if args.english and not os.path.exists(args.english):
        print(f"Error: English source file not found at {args.english}")
        sys.exit(1)
        
    print(f"Loading and aligning config data...")
    all_data = load_jsonl_config(args.config_path, args.english)
    total_tasks = len(all_data)
    print(f"Loaded a total of {total_tasks} tasks.")
    
    filename = os.path.basename(args.config_path)
    prefix = args.description_prefix or f"Batch upload for {filename}"
    
    batch_size = args.batch_size
    num_batches = (total_tasks + batch_size - 1) // batch_size
    
    test_ids = []
    
    # Import inside main to make sure Flask App Context is loaded
    from application.database import db
    from application.models import Test, Study
    from main import app
    
    for i in range(num_batches):
        start_idx = i * batch_size
        end_idx = min((i + 1) * batch_size, total_tasks)
        batch_data = all_data[start_idx:end_idx]
        
        description = f"{prefix} - Part {i+1} (Tasks {start_idx+1} to {end_idx})"
        print(f"\nLoading {len(batch_data)} tasks into database: '{description}'")
        
        with app.app_context():
            test = Test(
                id=db.session.query(db.func.max(Test.id)).scalar() + 1 if db.session.query(db.func.max(Test.id)).scalar() is not None else 1,
                test_type=TestType.TRANSLATION_CORRECTION.value,
                description=description,
                json_entry=batch_data
            )
            db.session.add(test)
            db.session.commit()
            
            if args.prolific:
                study_id = f"study_{test.id}"
                study = Study(
                    id=db.session.query(db.func.max(Study.id)).scalar() + 1 if db.session.query(db.func.max(Study.id)).scalar() is not None else 1,
                    test_id=test.id,
                    study_id=study_id,
                    completion_url=f"https://app.prolific.co/submissions/complete?cc=12345678"
                )
                db.session.add(study)
                db.session.commit()
                print(f"Created Prolific Study with Study ID: {study_id}")
                
            print(f"Successfully loaded Part {i+1}. Test ID: {test.id}")
            test_ids.append(test.id)
            
    print("\n" + "="*50)
    print("ALL BATCHES LOADED SUCCESSFULLY")
    print("="*50)
    for idx, tid in enumerate(test_ids):
        print(f"Part {idx+1}: Test ID = {tid}")
        print(f"  - Export command: python export_jsonl.py {tid} output_part_{idx+1}.jsonl")
    print("="*50)

if __name__ == "__main__":
    main()
