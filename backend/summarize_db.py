import sys
import os

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

def main():
    with app.app_context():
        tests = Test.query.all()
        if not tests:
            print("No task batches found in the database.")
            return
            
        print("=" * 95)
        print(f"{'Test ID':<10} | {'Description':<55} | {'Language':<12} | {'Total Tasks':<12}")
        print("=" * 95)
        
        for test in tests:
            desc = test.description or "No description"
            
            # Try to infer language
            lang = ""
            if test.json_entry and isinstance(test.json_entry, list) and len(test.json_entry) > 0:
                first_item = test.json_entry[0]
                lang = first_item.get('target_language') or first_item.get('language') or first_item.get('metadata', {}).get('language') or ""
                
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
            
            # Shorten description if too long
            if len(desc) > 52:
                desc = desc[:49] + "..."
                
            print(f"{test.id:<10} | {desc:<55} | {lang:<12} | {total_tasks:<12}")
            
        print("=" * 95)

if __name__ == "__main__":
    main()
