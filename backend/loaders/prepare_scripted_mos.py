import json
import os

input_path = '/root/tasks/scripted_mos.json'
output_path = '/root/saffron/backend/config/scripted_mos_en.json'

if not os.path.exists(input_path):
    print(f"Error: {input_path} does not exist.")
    exit(1)

with open(input_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# Filter for English and map to Saffron HFR format
saffron_tasks = []
id_counter = 1

for item in data:
    task_data = item.get("data", {})
    if task_data.get("language_id") == "en":
        saffron_task = {
            "id": id_counter,
            "audio_path": task_data.get("audio"),
            "label": "Human",  # Ground truth label (defaulting to Human for candidate samples)
            "description": task_data.get("candidate_name"),
            "attributes": {
                "candidate_name": task_data.get("candidate_name"),
                "duration_seconds": task_data.get("duration_seconds"),
                "source_audio_filepath": task_data.get("source_audio_filepath"),
                "language_id": "en"
            }
        }
        saffron_tasks.append(saffron_task)
        id_counter += 1

# Ensure directory exists
os.makedirs(os.path.dirname(output_path), exist_ok=True)

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(saffron_tasks, f, indent=2)

print(f"Successfully filtered and wrote {len(saffron_tasks)} English tasks to {output_path}")
