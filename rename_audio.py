import os
import glob

directories = [
    "/root/saffron/backend/audio_segmentation/set1",
    "/root/saffron/backend/audio_segmentation/set2"
]

# Set this to False to actually perform the rename operation
dry_run = False

for dir_path in directories:
    pattern = os.path.join(dir_path, "Copy of *")
    files = glob.glob(pattern)
    
    if not files:
        print(f"No files matching 'Copy of *' found in {dir_path}")
        continue
        
    print(f"\nProcessing directory: {dir_path} ({len(files)} files found)")
    for file_path in files:
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        
        # Remove 'Copy of ' prefix from the filename
        new_base_name = base_name.replace("Copy of ", "", 1)
        new_file_path = os.path.join(dir_name, new_base_name)
        
        if dry_run:
            print(f"[DRY-RUN] Would rename: '{base_name}' -> '{new_base_name}'")
        else:
            print(f"Renaming: '{base_name}' -> '{new_base_name}'")
            os.rename(file_path, new_file_path)
