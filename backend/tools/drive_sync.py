#!/usr/bin/env python3
"""Resumable, rate-limit tolerant download of a public Google Drive folder."""

import argparse
import json
import os
import random
import sys
import time
import urllib.request
import threading
import zipfile
from concurrent.futures import ThreadPoolExecutor

import gdown

LISTING_CACHE = 'drive_listing.json'


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def list_folder(url, out_dir, cache_path, refresh=False):
    """The folder's files as [{id, path}], cached so a re-run does not re-crawl."""
    if os.path.exists(cache_path) and not refresh:
        with open(cache_path, encoding='utf-8') as fh:
            files = json.load(fh)
        log(f"listing: {len(files)} file(s) from cache {cache_path}")
        return files
    log("listing folder from Drive (this takes a minute for a big folder)...")
    entries = gdown.download_folder(url, skip_download=True, quiet=True, output=out_dir)
    files = [{'id': f.id, 'path': f.path} for f in (entries or [])]
    with open(cache_path, 'w', encoding='utf-8') as fh:
        json.dump(files, fh, indent=1)
    log(f"listing: {len(files)} file(s) -> {cache_path}")
    return files


def is_complete(path):
    """A file counts as downloaded only if it is non-empty and, for xlsx, a readable zip -- a truncated download must not be mistaken for a good one."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    if path.lower().endswith(('.xlsx', '.docx', '.zip')):
        try:
            with zipfile.ZipFile(path) as z:
                return z.testzip() is None
        except Exception:
            return False
    return True


def _fetch(file_id, dest):
    """Pull the bytes straight from Drive's file host."""
    url = f'https://drive.usercontent.google.com/download?id={file_id}&export=download'
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (saffron-drive-sync)'})
    with urllib.request.urlopen(req, timeout=120) as r:
        head = r.read(512)
        # An HTML body means Drive served a quota/permission page, not the file.
        if head[:15].lower().lstrip().startswith(b'<!doctype') or head[:6].lower() == b'<html>':
            raise RuntimeError('Drive returned an HTML page instead of the file')
        with open(dest, 'wb') as fh:
            fh.write(head)
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)


def download_one(file_id, dest, tries, base_sleep):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(1, tries + 1):
        try:
            try:
                _fetch(file_id, dest)
            except Exception:
                gdown.download(id=file_id, output=dest, quiet=True)
            if is_complete(dest):
                return True
            raise RuntimeError('incomplete file on disk')
        except Exception as e:
            if os.path.exists(dest) and not is_complete(dest):
                try:
                    os.remove(dest)
                except OSError:
                    pass
            if attempt == tries:
                log(f"  FAILED {os.path.basename(dest)}: {e}")
                return False
            # Drive's "too many accesses" clears on its own -- back off and retry.
            wait = min(base_sleep * (2 ** (attempt - 1)), 300) * (0.7 + 0.6 * random.random())
            time.sleep(wait)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True, help='Drive folder URL')
    ap.add_argument('--out', required=True, help='local destination directory')
    ap.add_argument('--only', default='', help='only paths starting with this (e.g. Hindi)')
    ap.add_argument('--ext', default='.xlsx', help='comma-separated extensions to keep ("" = all)')
    ap.add_argument('--tries', type=int, default=6)
    ap.add_argument('--sleep', type=float, default=0.2, help='pause after each file (seconds)')
    ap.add_argument('--parallel', type=int, default=4, help='files downloaded at once')
    ap.add_argument('--backoff', type=float, default=20.0, help='first backoff after a failure')
    ap.add_argument('--refresh-listing', action='store_true')
    ap.add_argument('--listing', default='')
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    cache_path = args.listing or os.path.join(os.path.dirname(args.out.rstrip('/')) or '.',
                                              LISTING_CACHE)
    files = list_folder(args.url, args.out, cache_path, args.refresh_listing)

    exts = tuple(e.strip().lower() for e in args.ext.split(',') if e.strip())
    wanted = []
    for f in files:
        if args.only and not f['path'].lower().startswith(args.only.lower()):
            continue
        if exts and not f['path'].lower().endswith(exts):
            continue
        wanted.append(f)

    todo = [f for f in wanted if not is_complete(os.path.join(args.out, f['path']))]
    log(f"selected {len(wanted)} file(s); {len(wanted) - len(todo)} already on disk; "
        f"{len(todo)} to fetch")

    ok = fail = 0
    done = 0
    lock = threading.Lock()

    def fetch(entry):
        nonlocal ok, fail, done
        dest = os.path.join(args.out, entry['path'])
        good = download_one(entry['id'], dest, args.tries, args.backoff)
        with lock:
            done += 1
            if good:
                ok += 1
            else:
                fail += 1
            pct = 100.0 * done / len(todo)
            log(f"[{done}/{len(todo)} {pct:5.1f}%] ok={ok} fail={fail}  {entry['path']}")
        time.sleep(args.sleep)

    if todo:
        with ThreadPoolExecutor(max_workers=args.parallel) as pool:
            list(pool.map(fetch, todo))

    missing = [f['path'] for f in wanted
               if not is_complete(os.path.join(args.out, f['path']))]
    log(f"DONE: {len(wanted) - len(missing)}/{len(wanted)} present, {len(missing)} missing")
    if missing:
        with open(os.path.join(args.out, '_missing.txt'), 'w', encoding='utf-8') as fh:
            fh.write('\n'.join(missing))
        log(f"missing list -> {os.path.join(args.out, '_missing.txt')} (re-run to retry)")
    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
