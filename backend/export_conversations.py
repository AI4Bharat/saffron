import os
import sys
import json
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating
from main import app

def export_conversation_ratings(test_id: int, output_path: str, only_accepted: bool = False):
    with app.app_context():
        # 1. Fetch the original test
        test = Test.query.get(test_id)
        if not test:
            print(f"Error: Test ID {test_id} not found.")
            sys.exit(1)
            
        if test.test_type != "conversation-evaluation":
            print(f"Warning: Test ID {test_id} has type '{test.test_type}', not 'conversation-evaluation'.")
            
        original_items = test.json_entry
        if not isinstance(original_items, list):
            print("Error: Test json_entry is not a list.")
            sys.exit(1)
            
        # 2. Fetch all ratings/annotations for this test
        ratings = Rating.query.filter_by(test_id=test_id).filter(
            Rating.completion_status.in_(['completed', 'skipped'])
        ).all()
        
        # Group by page progress / task ID to get the latest rating
        latest_ratings = {}
        for rating in ratings:
            res_json = rating.results_json
            item_id = None
            
            if rating.page_no_progress is not None:
                item_id = rating.page_no_progress
            elif isinstance(res_json, dict) and 'id' in res_json:
                item_id = res_json['id']
                
            if item_id is None:
                continue
                
            # Convert to string to avoid type mismatch issues
            item_id_str = str(item_id)
            
            if item_id_str not in latest_ratings:
                latest_ratings[item_id_str] = rating
            else:
                existing_time = latest_ratings[item_id_str].time_of_submission
                current_time = rating.time_of_submission
                if current_time > existing_time:
                    latest_ratings[item_id_str] = rating
                    
        # 3. Process and merge
        output_items = []
        for item in original_items:
            item_id = item.get('id')
            item_id_str = str(item_id) if item_id is not None else ""
            
            # Deep copy original item
            item_copy = json.loads(json.dumps(item))
            
            if item_id_str in latest_ratings:
                rating = latest_ratings[item_id_str]
                rating_data = rating.results_json
                
                # Retrieve evaluation and comments
                evaluation = rating_data.get('evaluation')
                comments = rating_data.get('comments')
                
                # Check for filtering
                if only_accepted and evaluation != 'accept':
                    continue
                    
                item_copy['evaluation'] = evaluation
                item_copy['comments'] = comments
            else:
                # No rating found. If we want only accepted ones, skip it.
                if only_accepted:
                    continue
                item_copy['evaluation'] = None
                item_copy['comments'] = None
                
            output_items.append(item_copy)
            
        # 4. Write to JSONL
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as out_f:
            for line_item in output_items:
                out_f.write(json.dumps(line_item, ensure_ascii=False) + '\n')
                
        print(f"Successfully exported {len(output_items)} clean annotations to {output_path} (only_accepted={only_accepted})")

def main():
    parser = argparse.ArgumentParser(description="Export conversation evaluation ratings to a JSONL file")
    parser.add_argument("test_id", type=int, help="The database test ID to export")
    parser.add_argument("output_path", help="Output path for the JSONL file")
    parser.add_argument("--only-accepted", action="store_true", help="Only output conversations marked as accepted")
    
    args = parser.parse_args()
    export_conversation_ratings(args.test_id, args.output_path, args.only_accepted)

if __name__ == "__main__":
    main()
