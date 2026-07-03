import os
import sys
import pandas as pd
import json

# Add backend directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from main import app
from application.database import db
from application.models import Test

AUDIO_SEG_BASE_DIR = "/root/saffron/backend/audio_segmentation"
DEFAULT_SET = "set0"

def main():
    # Parse set name from command line or use default
    set_name = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SET
    
    # Normalize set_name (e.g. lowercase)
    set_name = set_name.lower().strip()
    
    audio_seg_dir = os.path.join(AUDIO_SEG_BASE_DIR, set_name)
    if not os.path.exists(audio_seg_dir):
        print(f"Error: Set directory not found at {audio_seg_dir}")
        print("Available sets in database directory:")
        if os.path.exists(AUDIO_SEG_BASE_DIR):
            for d in os.listdir(AUDIO_SEG_BASE_DIR):
                if os.path.isdir(os.path.join(AUDIO_SEG_BASE_DIR, d)):
                    print(f"  - {d}")
        sys.exit(1)
        
    # Find excel file dynamically in the set directory
    excel_files = [f for f in os.listdir(audio_seg_dir) if f.endswith(".xlsx") and not f.startswith("~$")]
    if not excel_files:
        print(f"Error: No Excel file (.xlsx) found in {audio_seg_dir}")
        sys.exit(1)
        
    excel_file = excel_files[0]
    excel_path = os.path.join(audio_seg_dir, excel_file)
        
    print(f"Reading Excel from {excel_path}...")
    df = pd.read_excel(excel_path)
    
    # Standardize columns
    print("Columns found in Excel:", df.columns)
    df.columns = [str(c).strip() for c in df.columns]
    if 'ID' not in df.columns and len(df.columns) > 0:
        df.rename(columns={df.columns[0]: 'ID'}, inplace=True)
    
    # We look for wav files in the set directory
    wav_files = [f for f in os.listdir(audio_seg_dir) if f.endswith(".wav")]
    print(f"Found {len(wav_files)} WAV files in {audio_seg_dir}")
    
    # Sort files to guarantee consistent order
    wav_files.sort()
    
    tasks = []
    for wav_file in wav_files:
        audio_id = os.path.splitext(wav_file)[0]
        
        # Find matching row in DataFrame
        row = df[df['ID'] == audio_id]
        if row.empty:
            print(f"Warning: No matching excel row for audio ID: {audio_id}")
            continue
            
        row_data = row.iloc[0]
        speaker = str(row_data['Speaker']).strip()
        
        # Clean up role (e.g. "Teacher)" -> "Teacher")
        role_raw = str(row_data.get('Unnamed: 2', 'Teacher')).strip()
        role = role_raw.rstrip(')').strip()
        
        transcript = str(row_data['Dialogue']).strip()
        
        # Get language and persona from excel name
        # English_Calm_Explainer_Set0.xlsx
        base_name = os.path.splitext(excel_file)[0]
        parts = base_name.split('_')
        
        language = parts[0] if len(parts) > 0 else "English"
        
        # Persona is Calm_Explainer -> Calm Explainer
        persona_parts = parts[1:-1] if len(parts) > 2 else parts[1:]
        persona = " ".join(persona_parts).title()
        
        # Save filename as "set_name/filename.wav" so views.py can serve it from the correct subdirectory
        task_item = {
            "id": audio_id,
            "audio_filename": f"{set_name}/{wav_file}",
            "transcript": transcript,
            "persona": persona,
            "speaker": speaker,
            "role": role,
            "language": language
        }
        tasks.append(task_item)
        print(f"Processed task {audio_id}: {speaker} ({role}) - {len(transcript)} chars")
        
    if not tasks:
        print("Error: No tasks were generated.")
        sys.exit(1)
        
    # Append the set name (e.g. Set0, Set1) to description to make it unique in the database
    description = f"Audio Segmentation - {language} - {persona} - {set_name.title()}"
    
    with app.app_context():
        # Check if description already exists
        existing_test = Test.query.filter_by(description=description).first()
        if existing_test:
            print(f"Test '{description}' already exists in DB with ID: {existing_test.id}")
            existing_test.json_entry = tasks
            existing_test.test_type = "audio-segmentation"
            db.session.commit()
            print(f"Updated existing Test ID={existing_test.id} with {len(tasks)} tasks.")
        else:
            next_id = (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1
            test = Test(
                id=next_id,
                test_type="audio-segmentation",
                description=description,
                json_entry=tasks
            )
            db.session.add(test)
            db.session.commit()
            print(f"Created new Test ID={next_id} '{description}' with {len(tasks)} tasks.")

if __name__ == "__main__":
    main()
