import sys
import os
import csv

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

def main():
    output_file = "/root/saffron/db_summary.csv"
    with app.app_context():
        tests = Test.query.all()
        if not tests:
            print("No task batches found in the database.")
            return
            
        with open(output_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Test ID', 'Description', 'Language', 'Total Tasks'])
            
            for test in tests:
                desc = test.description or "No description"
                
                # Try to infer language
                lang = ""
                if test.json_entry and isinstance(test.json_entry, list) and len(test.json_entry) > 0:
                    first_item = test.json_entry[0]
                    lang = first_item.get('target_language') or first_item.get('language') or first_item.get('metadata', {}).get('language') or ""
                
                desc = desc.replace("NCERT", "Secondary - Senior Secondary")
                    
                if not lang:
                    # Infer from description
                    desc_lower = desc.lower()
                    languages = ["hindi", "bengali", "gujarati", "kannada", "malayalam", "marathi", "odia", "tamil", "telugu", "urdu", "english"]
                    for l in languages:
                        if l in desc_lower:
                            lang = l.capitalize()
                            break
                
                if not lang:
                    lang = "Unknown"
                else:
                    lang = lang.capitalize()
                    
                total_tasks = len(test.json_entry) if test.json_entry else 0
                
                writer.writerow([test.id, desc, lang, total_tasks])
                
        print(f"Summary successfully written to {output_file}")

if __name__ == "__main__":
    main()
