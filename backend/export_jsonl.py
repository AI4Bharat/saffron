import json
import argparse
import sys
import os

# Add the parent directory or backend root to path to ensure imports work
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating
from main import app

def export_ratings_to_jsonl(test_id: int, output_path: str):
    with app.app_context():
        # 1. Fetch the original test definition
        test = Test.query.get(test_id)
        if not test:
            print(f"Error: Test ID {test_id} not found in the database.")
            sys.exit(1)
            
        print(f"Found test: ID={test.id}, Type={test.test_type}, Description={test.description}")
        
        # 2. Fetch all ratings/annotations for this test
        ratings = Rating.query.filter_by(test_id=test_id).filter(Rating.completion_status.in_(['completed', 'skipped'])).all()
        print(f"Found {len(ratings)} submissions in rating database.")
        
        # Group ratings by item/page ID, keeping the latest submission
        latest_ratings = {}
        for rating in ratings:
            res_json = rating.results_json
            item_id = None
            
            # The page progress or ID
            if rating.page_no_progress is not None:
                try:
                    item_id = int(rating.page_no_progress)
                except ValueError:
                    item_id = rating.page_no_progress
            elif isinstance(res_json, dict) and 'id' in res_json:
                item_id = res_json['id']
                
            if item_id is None:
                continue
                
            # Keep the latest submission
            if item_id not in latest_ratings:
                latest_ratings[item_id] = rating
            else:
                existing_time = latest_ratings[item_id].time_of_submission
                current_time = rating.time_of_submission
                if current_time > existing_time:
                    latest_ratings[item_id] = rating

        print(f"Extracted latest annotations for {len(latest_ratings)} distinct items.")

        # 3. Reconstruct the output JSONL by updating the original config data
        original_items = test.json_entry
        if not isinstance(original_items, list):
            print("Error: The test's json_entry is not a list.")
            sys.exit(1)
            
        output_lines = []
        for item in original_items:
            # Create a deep copy of the original item
            item_copy = json.loads(json.dumps(item))
            item_id = item_copy.get('id')
            
            if item_id in latest_ratings:
                rating = latest_ratings[item_id]
                rating_data = rating.results_json
                
                # Merge corrected pre_scene & post_scene if present in the rating
                if 'pre_scene' in rating_data:
                    item_copy['pre_scene'] = rating_data['pre_scene']
                if 'post_scene' in rating_data:
                    item_copy['post_scene'] = rating_data['post_scene']
                
                # Merge evaluation and comments if present
                if 'evaluation' in rating_data:
                    item_copy['evaluation'] = rating_data['evaluation']
                if 'comments' in rating_data:
                    item_copy['comments'] = rating_data['comments']
                
                # Case A: Dialog/conversation structure
                # Find dialogue keys in original and rating data (even if they differ, e.g. dialogue vs conversation)
                orig_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in item_copy and isinstance(item_copy[k], list)), None)
                rated_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in rating_data and isinstance(rating_data[k], list)), None)
                
                if orig_conv_key and rated_conv_key:
                    orig_list = item_copy[orig_conv_key]
                    rated_list = rating_data[rated_conv_key]
                    for i, orig_turn in enumerate(orig_list):
                        if i < len(rated_list):
                            rated_turn = rated_list[i]
                            # Copy over any non-English/non-role keys (the translation corrections)
                            for k, v in rated_turn.items():
                                if k not in ['role', 'english', 'english_text', 'original', 'original_text', 'en', 'text_en', 'speaker', 'user']:
                                    orig_turn[k] = v
                                        
                # Case B: Flat keys at top level (e.g. if the item itself was a single translation pair)
                translation_keys = ['translated', 'translation', 'translated_text', 'translated_sentence', 'text_translated', 'target', 'target_text']
                for k in translation_keys:
                    if k in item_copy and k in rating_data:
                        item_copy[k] = rating_data[k]
            
            # Clean up temporary English keys injected during loading
            item_copy.pop('pre_scene_en', None)
            item_copy.pop('post_scene_en', None)
            item_copy.pop('misconception_text_en', None)
            
            # Clean up dialogue turns
            for dialogue_key in ['dialogue', 'conversation', 'turns']:
                if dialogue_key in item_copy and isinstance(item_copy[dialogue_key], list):
                    for turn in item_copy[dialogue_key]:
                        turn.pop('english', None)
                        turn.pop('text_en', None)

            output_lines.append(item_copy)
            
        # 4. Write to output JSONL
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as out_f:
            for line_item in output_lines:
                out_f.write(json.dumps(line_item, ensure_ascii=False) + '\n')
                
        print(f"Successfully exported {len(output_lines)} clean annotations to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Export dialogue annotation corrections to JSONL')
    parser.add_argument('test_id', type=int, help='The database test ID to export')
    parser.add_argument('output_path', help='Output path for the JSONL file')
    
    args = parser.parse_args()
    
    export_ratings_to_jsonl(args.test_id, args.output_path)
