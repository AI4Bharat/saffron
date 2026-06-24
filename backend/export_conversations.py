import os
import sys
import json
import argparse
import re

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating
from main import app

# ----------------------------------------------------
# CONFIGURATION (Edit these variables directly in code)
# ----------------------------------------------------
TEST_IDS = [i for i in range(20098,20106)]  # List of Test IDs to export
OUTPUT_DIR = "/root/saffron/backend/exports"  # Directory where JSONL files will be saved
# ----------------------------------------------------

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9_ -]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'-+', '_', text)
    return text.strip('_')

def export_conversation_ratings(test_id: int, output_path: str, only_accepted: bool = False, comments_filter: str = 'all'):
    with app.app_context():
        # 1. Fetch the original test
        test = Test.query.get(test_id)
        if not test:
            print(f"Error: Test ID {test_id} not found.")
            return
            
        if test.test_type not in ["conversation-evaluation", "conversation-editable"]:
            print(f"Warning: Test ID {test_id} has type '{test.test_type}', not a conversation type.")
            
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
                
                # Check for evaluation filtering
                if only_accepted and evaluation != 'accept':
                    continue
                    
                # Check for comments filtering
                has_comments = bool(comments and str(comments).strip())
                if comments_filter == 'with' and not has_comments:
                    continue
                if comments_filter == 'without' and has_comments:
                    continue
                    
                item_copy['evaluation'] = evaluation
                item_copy['comments'] = comments
                
                # Merge corrected pre_scene & post_scene if present in the rating
                if 'pre_scene' in rating_data:
                    item_copy['pre_scene'] = rating_data['pre_scene']
                if 'post_scene' in rating_data:
                    item_copy['post_scene'] = rating_data['post_scene']
                
                # Merge conversation turn corrections
                orig_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in item_copy and isinstance(item_copy[k], list)), None)
                rated_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in rating_data and isinstance(rating_data[k], list)), None)
                
                if orig_conv_key and rated_conv_key:
                    orig_list = item_copy[orig_conv_key]
                    rated_list = rating_data[rated_conv_key]
                    for i, orig_turn in enumerate(orig_list):
                        if i < len(rated_list):
                            rated_turn = rated_list[i]
                            # Copy over any non-source/non-role keys (the dialogue text corrections)
                            for k, v in rated_turn.items():
                                if k not in ['role', 'english', 'english_text', 'original', 'original_text', 'en', 'text_en', 'speaker', 'user']:
                                    orig_turn[k] = v
            else:
                # No rating found.
                # If we filter only accepted or only with comments, skip this item.
                if only_accepted or comments_filter == 'with':
                    continue
                item_copy['evaluation'] = None
                item_copy['comments'] = None
                
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
                        
            output_items.append(item_copy)
            
        # 4. Write to JSONL
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            
        with open(output_path, 'w', encoding='utf-8') as out_f:
            for line_item in output_items:
                out_f.write(json.dumps(line_item, ensure_ascii=False) + '\n')
                
        print(f"Successfully exported {len(output_items)} clean annotations to {output_path} (only_accepted={only_accepted}, comments={comments_filter})")

def main():
    parser = argparse.ArgumentParser(description="Export conversation evaluation/editable ratings to JSONL files")
    parser.add_argument("--only-accepted", action="store_true", help="Only output conversations marked as accepted")
    parser.add_argument("--with-comments", action="store_true", help="Only output conversations that have comments")
    parser.add_argument("--without-comments", action="store_true", help="Only output conversations that do NOT have comments")
    
    args = parser.parse_args()
    
    comments_filter = 'all'
    if args.with_comments:
        comments_filter = 'with'
    elif args.without_comments:
        comments_filter = 'without'
        
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for test_id in TEST_IDS:
        print(f"\n--- Processing Test ID={test_id} ---")
        with app.app_context():
            test = Test.query.get(test_id)
            if not test:
                print(f"Error: Test ID {test_id} not found in database. Skipping.")
                continue
            desc_slug = slugify(test.description or f"test_{test_id}")
            filename = f"{test_id}_{test.test_type}_{desc_slug}.jsonl"
            output_path = os.path.join(OUTPUT_DIR, filename)
            
        export_conversation_ratings(test_id, output_path, args.only_accepted, comments_filter)

if __name__ == "__main__":
    main()
