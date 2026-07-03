#!/usr/bin/env python3
"""
Google Drive Audio Downloader (Robust Multi-file version with curl fallback)
==========================================================================
Downloads files from a Google Drive folder link or file link.
If a folder contains any restricted files, it will skip them and continue downloading the rest.
Uses direct curl downloads for fast and reliable downloads, bypassing gdown page scraping issues.
"""

# ==============================================================================
# CONFIGURATION
# ==============================================================================
# 1. Define the destination directory where files will be saved.
#    You can specify an absolute or relative path.
DOWNLOAD_DIR = "/root/saffron/backend/audio_segmentation/set1"

# 2. Paste your Google Drive folder or file link here.
#    Ensure the link sharing is set to "Anyone with the link".
DRIVE_LINK = "https://drive.google.com/drive/folders/1N8OPTK4GZAWDWhSBIZnG19fdyBi_4Q9K?usp=drive_link"
# ==============================================================================

import os
import sys
import subprocess
import json
import re

# Automatically ensure gdown is installed
try:
    import gdown
except ImportError:
    print("gdown package not found. Attempting to install it automatically...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "gdown"])
        import gdown
        print("Successfully installed gdown!\n")
    except Exception as e:
        print(f"Error: Failed to install 'gdown' package automatically. Details: {e}", file=sys.stderr)
        print("Please install gdown manually using: pip install gdown", file=sys.stderr)
        sys.exit(1)

def is_gdrive_folder(url):
    """
    Checks if a URL is a Google Drive folder link.
    """
    if "drive/folders" in url or "folders" in url:
        return True
    return False

def clean_url(url):
    return url.strip()

def get_folder_contents(url):
    """
    Use gdown CLI to list folder contents as JSON.
    """
    print("[*] Retrieving folder metadata from Google Drive...")
    try:
        cmd = ["gdown", url, "--folder", "--json"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return json.loads(result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"[-] Error listing folder contents via gdown CLI: {e.stderr}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[-] Error parsing folder contents metadata: {e}", file=sys.stderr)
        return None

def download_file_direct(url, output_path):
    """
    Attempts direct download using curl. Handles large file warnings from Google Drive.
    """
    match = re.search(r'(?:id=|\/d\/)([a-zA-Z0-9-_]+)', url)
    if not match:
        return False
    file_id = match.group(1)
    
    download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    # Try downloading directly
    cmd = ["curl", "-L", "-s", "-f", "--connect-timeout", "15", download_url, "-o", output_path]
    try:
        subprocess.run(cmd, check=True)
        
        # Check if the output is an HTML page (Google Drive virus scan warning or error)
        if os.path.exists(output_path) and os.path.getsize(output_path) < 25000:
            with open(output_path, 'r', errors='ignore') as f:
                content = f.read(20000)
                
                # Check for large file warning confirmation token
                if "confirm=" in content:
                    token_match = re.search(r'confirm=([a-zA-Z0-9-_]+)', content)
                    if token_match:
                        token = token_match.group(1)
                        confirm_url = f"{download_url}&confirm={token}"
                        cmd_confirm = ["curl", "-L", "-s", "-f", "--connect-timeout", "15", confirm_url, "-o", output_path]
                        subprocess.run(cmd_confirm, check=True)
                        return True
                        
                if "<html" in content.lower():
                    # It's an HTML error/login page, delete it
                    os.remove(output_path)
                    return False
        return True
    except Exception:
        if os.path.exists(output_path):
            os.remove(output_path)
        return False

def download_audios():
    url = clean_url(DRIVE_LINK)
    dest_dir = os.path.abspath(DOWNLOAD_DIR)
    
    if not url or "YOUR_GOOGLE_DRIVE_LINK_HERE" in url:
        print("[-] Error: Please update the 'DRIVE_LINK' variable at the top of the script with a valid Google Drive link.", file=sys.stderr)
        sys.exit(1)
        
    print(f"[*] Preparing download directory: {dest_dir}")
    os.makedirs(dest_dir, exist_ok=True)
    
    if is_gdrive_folder(url):
        print("[*] Detected Google Drive folder link.")
        files = get_folder_contents(url)
        if not files:
            print("[-] Could not retrieve folder contents. Trying standard gdown.download_folder as fallback...")
            try:
                gdown.download_folder(url=url, output=dest_dir, quiet=False, use_cookies=False)
                print(f"[+] Download complete to: {dest_dir}")
            except Exception as e:
                print(f"[-] Fallback folder download failed: {e}", file=sys.stderr)
            return

        total_files = len(files)
        print(f"[+] Found {total_files} files in the folder.")
        
        success_count = 0
        failed_files = []
        
        for idx, f in enumerate(files, 1):
            file_url = f.get("url")
            relative_path = f.get("path")
            
            if not file_url or not relative_path:
                continue
            
            # Auto-append .wav if the file in Google Drive has no extension
            if not relative_path.lower().endswith(".wav"):
                relative_path += ".wav"
                
            # Form target path
            target_path = os.path.join(dest_dir, relative_path)
            
            # Create subdirectories if needed (e.g. if the folder contains nested subfolders)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            
            filename = os.path.basename(target_path)
            print(f"\n[{idx}/{total_files}] Downloading '{filename}'...")
            
            if os.path.exists(target_path) and os.path.getsize(target_path) > 0:
                print(f"    [!] File already exists: {target_path}. Skipping.")
                success_count += 1
                continue
                
            # Try direct curl download first (much faster and avoids gdown blocking)
            success = download_file_direct(file_url, target_path)
            
            if not success:
                print("    [!] Direct download failed. Retrying with gdown...")
                try:
                    gdown.download(url=file_url, output=target_path, quiet=False, use_cookies=False)
                    success = True
                except Exception as e:
                    print(f"    [-] Error downloading '{filename}' with gdown: {e}", file=sys.stderr)
                    
            if success:
                success_count += 1
                print(f"    [+] Successfully downloaded: {filename}")
            else:
                failed_files.append((filename, file_url))
                
        print("\n" + "="*50)
        print(f"DOWNLOAD SUMMARY:")
        print(f"Total files found: {total_files}")
        print(f"Successfully downloaded/verified: {success_count}")
        print(f"Failed downloads: {len(failed_files)}")
        if failed_files:
            print("\nThe following files failed to download (likely due to restricted access permissions):")
            for fname, furl in failed_files:
                print(f" - {fname} (ID: {furl.split('id=')[-1] if 'id=' in furl else furl})")
        print("="*50)
        
    else:
        print("[*] Detected Google Drive single file link (or fallback).")
        try:
            gdown.download(url=url, output=dest_dir, quiet=False, use_cookies=False, fuzzy=True)
            print(f"\n[+] Success! File downloaded/extracted to: {dest_dir}")
        except Exception as e:
            print(f"\n[-] Error downloading file: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    download_audios()
