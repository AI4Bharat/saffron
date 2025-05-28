import os
import sys
import logging
from azure.storage.blob import BlobServiceClient, BlobSasPermissions, generate_blob_sas
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv(".env")

# Configure logging
LOG_FILE = f"/root/tts-saffron/backend/logs/db_backup-{datetime.now().strftime('%Y-%m-%d')}.log"
logging.basicConfig(filename=LOG_FILE,
                    level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

def upload_backup_to_azure(backup_file):
    try:
        # Check if the backup file exists
        if not os.path.exists(backup_file):
            logging.error(f"File not found: {backup_file}")
            sys.exit(2)  # Custom exit code for file not found

        # Ensure all required environment variables are present
        azure_account_url = os.environ.get("AZURE_ACCOUNT_URL")
        credential = os.environ.get("CREDENTIAL")
        container_name = os.environ.get("DATABASE_CONTAINER")
        if not all([azure_account_url, credential, container_name]):
            logging.error("Missing necessary environment variables.")
            sys.exit(3)  # Custom exit code for missing environment variables

        # Initialize the BlobServiceClient and ContainerClient
        blob_service_client = BlobServiceClient(account_url=azure_account_url, credential=credential)
        container_client = blob_service_client.get_container_client(container_name)

        # Determine blob name based on the backup file's relative path
        blob_name = os.path.relpath(backup_file, "/tmp")
        logging.info(f"Uploading {backup_file} as blob {blob_name}")

        # Upload the file to Azure Blob Storage
        blob_client = container_client.get_blob_client(blob_name)
        with open(backup_file, 'rb') as data:
            blob_client.upload_blob(data, overwrite=True)

        logging.info(f"Upload completed for {blob_name}")

        # Generate SAS token for the uploaded blob to create a download URL
        sas_token = generate_blob_sas(
            account_name=blob_service_client.account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=credential,
            permission=BlobSasPermissions(read=True),
            expiry=datetime.utcnow() + timedelta(days=120)  # SAS token valid for 120 days
        )

        # Construct the download URL with SAS token
        download_url = f"{azure_account_url}/{container_name}/{blob_name}?{sas_token}"
        logging.info(f"Download URL for {blob_name}: {download_url}")

    except Exception as e:
        # Catch and log any exceptions that occur during the process
        logging.error(f"An error occurred: {str(e)}")
        sys.exit(4)  # Custom exit code for errors during execution

    finally:
        logging.info("Backup process completed.")

if __name__ == "__main__":
    # Ensure a backup file is provided as a command-line argument
    if len(sys.argv) != 2:
        logging.error("Backup file path must be provided as a command-line argument.")
        sys.exit(5)  # Custom exit code for missing argument

    backup_file = sys.argv[1]
    upload_backup_to_azure(backup_file)
