#!/usr/bin/env python3
"""Pull the segmented clips out of Drive, keeping the folder layout.

    /data2/segmented_audios/<Language>/<Artist_Persona>/<... Set N>/ID/<clip>.wav

gdown's folder downloader stops at 50 files, so each clip is fetched by its own
id instead. Resumable: a file already on disk with a non-zero size is left
alone, so the script can be re-run after an interruption.
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import gdown

URL = "https://drive.google.com/drive/folders/1oQ3T8_eIR6Za7dKuSrJRturrivQEKxns"
DEST = "/data2/segmented_audios"
LIST_CACHE = "/tmp/segmented_listing.json"


def listing():
    """(id, relative path) for every file, cached so Drive is scanned once."""
    if os.path.exists(LIST_CACHE):
        return [tuple(x) for x in json.load(open(LIST_CACHE))]
    for attempt in range(5):
        try:
            fs = gdown.download_folder(url=URL, skip_download=True, quiet=True) or []
            out = [(f.id, f.path.replace("\\", "/")) for f in fs]
            json.dump(out, open(LIST_CACHE, "w"))
            return out
        except Exception as e:
            wait = 20 * (attempt + 1)
            print("  [retry %d] %s -- %ds" % (attempt + 1, str(e)[:80], wait), flush=True)
            time.sleep(wait)
    sys.exit("  could not list the Drive folder")


def fetch(item):
    fid, rel = item
    dest = os.path.join(DEST, rel)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return ("skip", rel)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    for attempt in range(3):
        try:
            got = gdown.download(id=fid, output=dest, quiet=True)
            if got and os.path.getsize(dest) > 0:
                return ("ok", rel)
        except Exception as e:
            last = str(e)[:120]
            time.sleep(3 * (attempt + 1))
    else:
        last = "empty file"
    if os.path.exists(dest) and os.path.getsize(dest) == 0:
        os.remove(dest)
    return ("fail", "%s :: %s" % (rel, last))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    files = listing()
    if args.limit:
        files = files[:args.limit]
    print("  files in the Drive folder: %d" % len(files), flush=True)

    done = {"ok": 0, "skip": 0, "fail": 0}
    fails = []
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(fetch, f) for f in files]
        for i, fu in enumerate(as_completed(futs), 1):
            state, info = fu.result()
            done[state] += 1
            if state == "fail":
                fails.append(info)
            if i % 250 == 0 or i == len(files):
                el = time.time() - t0
                print("  %5d/%d  ok=%d skip=%d fail=%d  %.1f files/s"
                      % (i, len(files), done["ok"], done["skip"], done["fail"],
                         i / el if el else 0), flush=True)

    print()
    print("  downloaded : %d" % done["ok"])
    print("  already there: %d" % done["skip"])
    print("  failed     : %d" % done["fail"])
    if fails:
        with open("/tmp/segmented_failures.txt", "w") as fh:
            fh.write("\n".join(fails))
        print("  failures written to /tmp/segmented_failures.txt")
        for f in fails[:10]:
            print("     ", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
