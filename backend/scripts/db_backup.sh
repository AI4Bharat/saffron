#!/bin/bash

# Exit the script on any error
set -e

cd /root/tts-saffron/backend

# Function to upload a file to Azure Blob Storage
upload_to_azure() {
    local backup_file=$1
    echo "$(date) - Starting upload of ${backup_file}." >> /root/tts-saffron/backend/logs/db_backup.log

    if [ -f "$backup_file" ]; then
        # Activate Conda environment
        source /root/miniconda3/etc/profile.d/conda.sh
        conda activate qa

        # Run Python script to upload the file
        python /root/tts-saffron/backend/database_bkp.py "$backup_file"
        local python_status=$?

        # Deactivate Conda environment
        conda deactivate

        if [ $python_status -ne 0 ]; then
            echo "$(date) - ERROR: Upload of ${backup_file} failed. Python script error." >> /root/tts-saffron/backend/logs/db_backup.log
            exit 1
        else
            echo "$(date) - Upload of ${backup_file} completed." >> /root/tts-saffron/backend/logs/db_backup.log
        fi
    else
        echo "$(date) - File ${backup_file} not found. Skipping upload." >> /root/tts-saffron/backend/logs/db_backup.log
        exit 1
    fi
}

# Trap any errors and log them
trap 'echo "$(date) - ERROR: Script failed." >> /root/tts-saffron/backend/logs/db_backup.log' ERR

echo "$(date) - cronjob started" >> /root/tts-saffron/backend/logs/db_backup.log

# Set the date format for the backup file
BACKUP_DATE=$(date +\%Y-\%m-\%d-\%H-\%M-\%S)

# Define backup files
BACKUP_FILE_1="/var/backups/saffron-$BACKUP_DATE"

# Perform the database backup
echo "$(date) - Starting database backup." >> /root/tts-saffron/backend/logs/db_backup.log
PGPASSWORD='ai4b_tts' sudo -u postgres pg_dump -U postgres -d saffron -f "$BACKUP_FILE_1"
if [ $? -ne 0 ]; then
    echo "$(date) - ERROR: Database backup failed." >> /root/tts-saffron/backend/logs/db_backup.log
    exit 1
else
    echo "$(date) - Database backup completed." >> /root/tts-saffron/backend/logs/db_backup.log
fi

# Upload each backup file
upload_to_azure "$BACKUP_FILE_1"

# Log end of cron job
echo "$(date) - cronjob ended successfully" >> /root/tts-saffron/backend/logs/db_backup.log
echo "done"

cd
