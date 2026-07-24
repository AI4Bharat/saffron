import os
import sys
import json
import argparse

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

CONVERSATIONS_DIR = "/root/saffron/backend/conversation_tasks"

def format_description(filename):
    # Strip extension
    base = os.path.splitext(filename)[0]
    if base.startswith("conversations_"):
        base = base[len("conversations_"):]
    
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
    
    return f"Conversation Evaluation - {lang} - {persona} - {grade}"

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
    parser = argparse.ArgumentParser(description="Load all conversation files into the database as separate tests")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing to database")
    args = parser.parse_args()
    
    if not os.path.exists(CONVERSATIONS_DIR):
        print(f"Error: Directory {CONVERSATIONS_DIR} does not exist.")
        sys.exit(1)
        
    files = sorted([f for f in os.listdir(CONVERSATIONS_DIR) if f.endswith(".jsonl")])
    print(f"Found {len(files)} JSONL files in {CONVERSATIONS_DIR}.")
    
    with app.app_context():
        # Get existing descriptions to prevent duplicates
        existing_descriptions = {t.description for t in Test.query.with_entities(Test.description).all() if t.description}
        
        next_id = (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1
        created_count = 0
        skipped_count = 0
        
        for file in files:
            file_path = os.path.join(CONVERSATIONS_DIR, file)
            description = format_description(file)
            
            if description in existing_descriptions:
                print(f"[SKIP] Test '{description}' already exists.")
                skipped_count += 1
                continue
                
            data = load_jsonl(file_path)
            num_tasks = len(data)
            
            if args.dry_run:
                print(f"[DRY RUN] Would create Test ID={next_id} '{description}' with {num_tasks} tasks.")
            else:
                test = Test(
                    id=next_id,
                    test_type="conversation-evaluation",
                    description=description,
                    json_entry=data
                )
                db.session.add(test)
                db.session.commit()
                print(f"[CREATED] Test ID={next_id} '{description}' with {num_tasks} tasks.")
                
            next_id += 1
            created_count += 1
            
        print("\n" + "="*50)
        print(f"Done: {created_count} tests created, {skipped_count} skipped.")
        print("="*50)

if __name__ == "__main__":
    main()
