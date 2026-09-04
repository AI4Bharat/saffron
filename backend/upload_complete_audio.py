#!/usr/bin/env python3
"""Put the full session recordings into the bucket, keeping Drive's layout.

    aivanta_complete_audio/<Language>/<Persona - Artist>/<file>.wav

These are the unsegmented takes, one per recording session, as distinct from
aivanta_dataset/ which holds the reviewed clips.

Resumable: an object already there at the same size is skipped.
"""
import argparse
import os
os.environ["SAFFRON_SKIP_BOOT_MIGRATIONS"] = "1"
import sys
import time
from collections import defaultdict

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv("/root/saffron/backend/.env")

SRC = "/data2/aivanta_complete_audio"
ROOT = "aivanta_complete_audio"
BUCKET = os.getenv("S3_BUCKET")

README = """# Aivanta complete audio

The full session recordings, one file per recording session, exactly as the
voice artists delivered them.

    <Language>/<Persona> - <Artist>/<session>.wav

These are unsegmented: a single file covers a whole set, sometimes several.
The reviewed, clip-level audio lives under `aivanta_dataset/` instead, split
into accepted and rejected with a manifest per set.
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if not BUCKET:
        sys.exit("  S3_BUCKET is not configured")

    cli = boto3.client("s3", endpoint_url=os.getenv("S3_ENDPOINT"),
                       aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
                       aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
                       region_name=os.getenv("S3_REGION", "us-east-1"),
                       config=Config(signature_version="s3v4",
                                     s3={"addressing_style": "path"},
                                     retries={"max_attempts": 5}))

    files = []
    for root, _d, fs in os.walk(SRC):
        for f in sorted(fs):
            if f.endswith(".part"):
                continue
            p = os.path.join(root, f)
            files.append((p, os.path.relpath(p, SRC).replace("\\", "/")))
    files.sort(key=lambda x: x[1])
    print("  files to place: %d" % len(files))

    uploaded = skipped = 0
    moved = 0
    per_lang = defaultdict(lambda: [0, 0])
    t0 = time.time()

    for i, (path, rel) in enumerate(files, start=1):
        key = "%s/%s" % (ROOT, rel)
        size = os.path.getsize(path)
        lang = rel.split("/")[0]
        per_lang[lang][0] += 1
        per_lang[lang][1] += size

        try:
            head = cli.head_object(Bucket=BUCKET, Key=key)
            if head.get("ContentLength") == size:
                skipped += 1
                continue
        except ClientError:
            pass

        if args.dry_run:
            uploaded += 1
            continue
        cli.upload_file(path, BUCKET, key, ExtraArgs={"ContentType": "audio/wav"})
        uploaded += 1
        moved += size
        if i % 10 == 0 or i == len(files):
            print("  [%3d/%d] %.1f GB placed" % (i, len(files), moved / 1024.0 ** 3))
            sys.stdout.flush()

    if not args.dry_run:
        cli.put_object(Bucket=BUCKET, Key=ROOT + "/README.md",
                       Body=README.encode("utf-8"), ContentType="text/markdown")

    print()
    for lang, (n, b) in sorted(per_lang.items()):
        print("  %-10s %3d file(s)  %.2f GB" % (lang, n, b / 1024.0 ** 3))
    print()
    print("  uploaded : %d" % uploaded)
    print("  skipped  : %d (already there)" % skipped)
    print("  moved    : %.2f GB" % (moved / 1024.0 ** 3))
    print("  elapsed  : %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
