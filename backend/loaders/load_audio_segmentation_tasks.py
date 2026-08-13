import os
import re
import sys
import pandas as pd
import json

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend root

from main import app
from application.database import db
from application.models import Test, Team

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
        
        # Get language and persona from excel name English_Calm_Explainer_Set0.xlsx
        base_name = os.path.splitext(excel_file)[0]
        parts = base_name.split('_')
        
        language = parts[0] if len(parts) > 0 else "English"
        
        # Persona is Calm_Explainer -> Calm Explainer
        persona_parts = parts[1:-1] if len(parts) > 2 else parts[1:]
        persona = " ".join(persona_parts).title()
        
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
        
    # The set number shown in the UI is the RECORDING EXCEL's set (e.g.
    m_set = re.search(r"_Set(\d+)$", os.path.splitext(excel_file)[0], re.IGNORECASE)
    set_label = f"Set{int(m_set.group(1))}" if m_set else set_name.title()
    description = f"Audio Segmentation - {language} - {persona} - {set_label}"

    # Record which local dir this batch came from so the row can be identified even when two batches share an excel set (e.g.
    for t in tasks:
        t["set_dir"] = set_name
        t["excel_set"] = set_label

    with app.app_context():
        # Identify an existing row by its SET DIR (unique), not by description -- descriptions may legitimately repeat now that they use the excel set.
        existing_test = None
        for t in Test.query.filter_by(test_type="audio-segmentation").all():
            entries = t.json_entry if isinstance(t.json_entry, list) else []
            if entries and str(entries[0].get("audio_filename", "")).split("/")[0] == set_name:
                existing_test = t
                break
        # Batches are team-scoped on the dashboard: a Test without team_id is invisible to every team admin (the old boot backfill that patched this up at the NEXT restart is retired), so stamp the owning team here.
        owner = Team.query.filter_by(
            key=os.environ.get('AUDIO_SEG_TEAM_KEY', 'tts')).first()
        if existing_test:
            print(f"Test for dir '{set_name}' already exists in DB with ID: {existing_test.id}")
            existing_test.json_entry = tasks
            existing_test.description = description
            existing_test.test_type = "audio-segmentation"
            if existing_test.team_id is None and owner:
                existing_test.team_id = owner.id
            existing_test.item_count = len(tasks)
            existing_test.language_hint = language.lower()
            db.session.commit()
            print(f"Updated existing Test ID={existing_test.id} '{description}' with {len(tasks)} tasks.")
        else:
            next_id = (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1
            test = Test(
                id=next_id,
                test_type="audio-segmentation",
                description=description,
                json_entry=tasks,
                team_id=owner.id if owner else None,
                item_count=len(tasks),
                language_hint=language.lower(),
            )
            db.session.add(test)
            db.session.commit()
            print(f"Created new Test ID={next_id} '{description}' with {len(tasks)} tasks.")

        # Recompute every audio-segmentation label: sets recorded/loaded as more than one batch get "(Recorder, Conv X-Y)" appended so they are told apart.
        try:
            import audio_set_labels
            print("Refreshing audio-segmentation labels...")
            audio_set_labels.relabel_all(db, Test)
        except Exception as e:
            print(f"[WARN] Could not refresh labels: {e}")

if __name__ == "__main__":
    main()
