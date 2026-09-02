#!/usr/bin/env python3
"""Write the voice artist for audio sets, so the Quality dashboard stops
showing 'Unknown'.

The dashboard reads the artist from <set_dir>/recorder.txt and nothing else in
the system records it -- the 'speaker' field on an item is the character in the
script, not the person who recorded it. So the names have to be supplied.

Fill the 'artist' column of the CSV and run this. Rows left blank are skipped,
so it can be run repeatedly as names arrive.

    python apply_set_artists.py --csv set_artists.csv --dry-run
    python apply_set_artists.py --csv set_artists.csv
"""
import argparse
import csv
import io
import os
import sys

AUDIO_DIR = "/root/saffron/backend/audio_segmentation"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="replace a recorder.txt that already has a name")
    args = ap.parse_args()

    with io.open(args.csv, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    wrote = skipped = blank = missing = kept = 0
    for r in rows:
        set_dir = (r.get("set_dir") or "").strip()
        artist = (r.get("artist") or "").strip()
        if not set_dir:
            continue
        if not artist:
            blank += 1
            continue

        d = os.path.join(AUDIO_DIR, set_dir)
        if not os.path.isdir(d):
            print("  MISSING DIR  %-8s (skipped)" % set_dir)
            missing += 1
            continue

        p = os.path.join(d, "recorder.txt")
        existing = ""
        if os.path.isfile(p):
            try:
                existing = open(p, encoding="utf-8").read().strip()
            except Exception:
                existing = ""
        if existing and not args.overwrite:
            if existing != artist:
                print("  KEPT         %-8s already '%s' (use --overwrite to replace with '%s')"
                      % (set_dir, existing, artist))
            kept += 1
            continue

        if args.dry_run:
            print("  would write  %-8s %s" % (set_dir, artist))
            skipped += 1
            continue

        # Written the same way the existing files read: the bare name, one line.
        tmp = p + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as fh:
            fh.write(artist + "\n")
        os.replace(tmp, p)
        print("  wrote        %-8s %s" % (set_dir, artist))
        wrote += 1

    print()
    print("  rows in csv        : %d" % len(rows))
    print("  artist left blank  : %d" % blank)
    print("  already named      : %d" % kept)
    print("  set dir not found  : %d" % missing)
    if args.dry_run:
        print("  WOULD write        : %d   (dry run -- nothing changed)" % skipped)
    else:
        print("  written            : %d" % wrote)
        if wrote:
            print("\n  The dashboard caches artists per process; the names appear")
            print("  after the next backend reload (kill -HUP the gunicorn master).")


if __name__ == "__main__":
    main()
