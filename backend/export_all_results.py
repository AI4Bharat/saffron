import os
import sys
import re
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.models import Test
from export_conversations import export_conversation_ratings
from export_jsonl import export_ratings_to_jsonl

EXPORT_DIR = "/root/saffron/backend/exports"

def slugify(text):
    text = text.lower()
    text = re.sub(r'[^a-z0-9_ -]', '', text)
    text = re.sub(r'\s+', '_', text)
    text = re.sub(r'-+', '_', text)
    return text.strip('_')

def main():
    parser = argparse.ArgumentParser(description="Bulk export all test results from the database to JSONL files")
    parser.add_argument("--output-dir", default=EXPORT_DIR, help="Directory to save exported JSONL files")
    parser.add_argument("--only-accepted", action="store_true", help="For conversation evaluation tests, only export accepted items")
    args = parser.parse_args()
    
    os.makedirs(args.output_dir, exist_ok=True)
    
    with app.app_context():
        tests = Test.query.all()
        if not tests:
            print("No tests found in database to export.")
            return
            
        print(f"Starting bulk export of {len(tests)} tests to {args.output_dir}...")
        
        for test in tests:
            desc_slug = slugify(test.description or f"test_{test.id}")
            filename = f"{test.id}_{test.test_type}_{desc_slug}.jsonl"
            output_path = os.path.join(args.output_dir, filename)
            
            print(f"\n--- Exporting Test ID={test.id} (Type: {test.test_type}) ---")
            
            if test.test_type in ["conversation-evaluation", "conversation-editable"]:
                try:
                    export_conversation_ratings(test.id, output_path, args.only_accepted)
                except Exception as e:
                    print(f"Error exporting Test {test.id} ({test.test_type}): {e}")
            else:
                # Handle existing test types using original exporter
                try:
                    export_ratings_to_jsonl(test.id, output_path)
                except Exception as e:
                    print(f"Error exporting Test {test.id} ({test.test_type}): {e}")
                    
        print(f"\nBulk export completed. Files saved to {args.output_dir}.")

if __name__ == "__main__":
    main()
