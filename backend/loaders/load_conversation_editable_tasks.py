import os
import sys
import json
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

CONVERSATIONS_DIRS = [
    "/root/saffron/backend/tasks/tts/conversation_editable_tasks"
]

def format_description(filename, subfolder=None):
    # Strip extension
    base = os.path.splitext(filename)[0]
    if base.startswith("conversations_"):
        base = base[len("conversations_"):]
    elif base.startswith("conversation_"):
        base = base[len("conversation_"):]
    
    # Split tokens
    tokens = base.split("_")
    
    # Parse language (first token)
    lang = tokens[0].capitalize()
    
    # Find persona and grade
    grade_tokens = []
    persona_tokens = []
    
    is_grade = False
    for t in tokens[1:]:
        if t in ["elementary", "middle", "secondary", "senior"]:
            is_grade = True
        if is_grade:
            grade_tokens.append(t)
        else:
            persona_tokens.append(t)
            
    persona = " ".join(persona_tokens).title()
    grade = " ".join(grade_tokens).title()
    
    suffix = "Editable"
    desc = f"Conversation {suffix} - {lang} - {persona} - {grade}"
    if subfolder:
        clean_subfolder = subfolder.replace("_", " ").replace("-", " ").replace("/", " / ").title()
        desc += f" - {clean_subfolder}"
    return desc

def load_jsonl(path):
    import re
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                pattern = r'(?<!\\)\\(times|theta|tau|to|text|tfrac|triangle|frac|phi|varphi|forall|beta|binom|bar|bullet|bot|begin|tilde|tan|top|textrm|textbf|textit)\b'
                fixed_line = re.sub(pattern, r'\\\\\1', line)
                item = json.loads(fixed_line)
                data.append(item)
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON on line {idx} in {path}: {e}")
                sys.exit(1)
    return data

def main():
    parser = argparse.ArgumentParser(description="Load all editable conversation files into the database as separate tests")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to database")
    parser.add_argument("--batch-size", type=int, default=None, help="Number of tasks per batch")
    parser.add_argument("--exclude-english", action="store_true", help="Exclude English tasks (files containing 'english' in name)")
    parser.add_argument("--subfolder", type=str, default=None, help="Only process files in this subfolder (e.g. version_5)")
    args = parser.parse_args()
    
    conversations_dir = None
    for d in CONVERSATIONS_DIRS:
        if os.path.exists(d):
            conversations_dir = d
            break
            
    if not conversations_dir:
        print(f"Error: Neither of editable conversation directories exists: {CONVERSATIONS_DIRS}")
        sys.exit(1)
        
    # Walk recursively to find all jsonl files
    files_to_load = []
    for root, dirs, files in os.walk(conversations_dir):
        # Sort files to guarantee consistent order
        for file in sorted(files):
            if file.endswith(".jsonl"):
                rel_dir = os.path.relpath(root, conversations_dir)
                subfolder = None if rel_dir == "." else rel_dir
                
                # Check subfolder filter
                if args.subfolder:
                    if not subfolder:
                        continue
                    if args.subfolder.strip('/').lower() != subfolder.strip('/').lower():
                        continue
                        
                # Check exclude English
                if args.exclude_english:
                    if "english" in file.lower():
                        continue
                        
                file_path = os.path.join(root, file)
                files_to_load.append((file_path, file, subfolder))
                
    # Sort files_to_load by subfolder and filename for predictability
    files_to_load.sort(key=lambda x: (x[2] or "", x[1]))
    
    print(f"Found {len(files_to_load)} JSONL files to process in {conversations_dir} (after filtering).")
    
    with app.app_context():
        # Get existing descriptions to prevent duplicates
        existing_descriptions = {t.description for t in Test.query.with_entities(Test.description).all() if t.description}
        
        next_id = (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1
        created_count = 0
        skipped_count = 0
        
        for file_path, file, subfolder in files_to_load:
            description = format_description(file, subfolder)
            data = load_jsonl(file_path)
            num_tasks = len(data)
            
            if args.batch_size:
                batch_size = args.batch_size
                num_batches = (num_tasks + batch_size - 1) // batch_size
                for i in range(num_batches):
                    start_idx = i * batch_size
                    end_idx = min((i + 1) * batch_size, num_tasks)
                    batch_data = data[start_idx:end_idx]
                    
                    batch_desc = f"{description} - Part {i+1} (Tasks {start_idx+1} to {end_idx})"
                    
                    if batch_desc in existing_descriptions:
                        print(f"[SKIP] Test '{batch_desc}' already exists.")
                        skipped_count += 1
                        continue
                        
                    if args.dry_run:
                        print(f"[DRY RUN] Would create Test ID={next_id} '{batch_desc}' with {len(batch_data)} tasks.")
                    else:
                        test = Test(
                            id=next_id,
                            test_type="conversation-editable",
                            description=batch_desc,
                            json_entry=batch_data
                        )
                        db.session.add(test)
                        db.session.commit()
                        print(f"[CREATED] Test ID={next_id} '{batch_desc}' with {len(batch_data)} tasks.")
                        
                    next_id += 1
                    created_count += 1
            else:
                if description in existing_descriptions:
                    print(f"[SKIP] Test '{description}' already exists.")
                    skipped_count += 1
                    continue
                    
                if args.dry_run:
                    print(f"[DRY RUN] Would create Test ID={next_id} '{description}' with {num_tasks} tasks.")
                else:
                    test = Test(
                        id=next_id,
                        test_type="conversation-editable",
                        description=description,
                        json_entry=data
                    )
                    db.session.add(test)
                    db.session.commit()
                    print(f"[CREATED] Test ID={next_id} '{description}' with {num_tasks} tasks.")
                    
                next_id += 1
                created_count += 1
            
        print("\n" + "="*50)
        print(f"Done: {created_count} tests/parts created, {skipped_count} skipped.")
        print("="*50)

    try:
        from update_status_report import update_status
        update_status()
    except Exception as e:
        print(f"Warning: Could not auto-update status report: {e}")

if __name__ == "__main__":
    main()
