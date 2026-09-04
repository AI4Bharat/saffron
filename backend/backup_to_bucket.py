#!/usr/bin/env python3
"""Back the finished QC up to the object store, arranged for a human to browse.

    <Language>/<Persona>/Set<N>/
        accepted/<clip>.wav
        rejected/<clip>.wav
        manifest.jsonl     one row per clip: script, verdict, reasons, reviewer
        manifest.csv       the same, for spreadsheets
        script.xlsx        the recording sheet the set came from, when present
    SUMMARY.md             what is in the backup
    README.md              the layout and what each field means

Only sets where every clip has a verdict are included; a set still being
reviewed would otherwise look finished once it was copied.

Resumable: an object already present with the same byte size is skipped, so a
re-run costs almost nothing and an interrupted run can simply be repeated.

    python backup_to_bucket.py --dry-run
    python backup_to_bucket.py
    python backup_to_bucket.py --only Telugu
"""
import argparse
import csv
import io
import os
os.environ["SAFFRON_SKIP_BOOT_MIGRATIONS"] = "1"
import json
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, "/root/saffron/backend")

import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv

load_dotenv("/root/saffron/backend/.env")

from main import app
from application.models import Test, Rating, Rater

AUDIO_DIR = "/root/saffron/backend/audio_segmentation"
BUCKET = os.getenv("S3_BUCKET")
ROOT = "aivanta_dataset"

FIELDS = ["clip_id", "verdict", "language", "persona", "set", "artist", "speaker",
          "role", "script", "rejection_reasons", "notes", "reviewer",
          "reviewed_at", "audio_path", "bytes", "test_id"]

README = """# Aivanta dataset

Audio-segmentation clips whose review is finished, with the script that was
recorded and the verdict each clip received.

## Layout

    <Language>/<Persona>/Set<N>/
        accepted/<clip>.wav      clips the reviewer accepted
        rejected/<clip>.wav      clips the reviewer rejected
        manifest.jsonl           one JSON object per clip
        manifest.csv             the same rows, for spreadsheets
        script.xlsx              the recording sheet this set came from

A clip's folder IS its verdict, so the accepted set can be taken wholesale
without reading the manifest.

## Fields

| field | meaning |
|---|---|
| `clip_id` | identifier of the clip inside its conversation |
| `verdict` | `accepted` or `rejected` |
| `artist` | the voice artist who recorded the set |
| `speaker` | the character speaking in the script, not the artist |
| `script` | the line as recorded |
| `rejection_reasons` | why it was rejected; empty when accepted |
| `notes` | free text the reviewer left |
| `reviewer` | who reviewed it |
| `reviewed_at` | when, in UTC |
| `audio_path` | this clip's key inside the backup |

Only sets where every clip has a verdict are here. Sets still under review are
left out until they are finished.
"""


def s3():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("S3_ENDPOINT"),
        aws_access_key_id=os.getenv("S3_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("S3_SECRET_KEY"),
        region_name=os.getenv("S3_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"},
                      retries={"max_attempts": 5}),
    )


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "").strip()).strip("_") or "Unknown"


def parts_of(desc):
    bits = [b.strip() for b in (desc or "").split(" - ")]
    lang = bits[1] if len(bits) > 2 else "Unknown"
    persona = bits[2] if len(bits) > 3 else "Unknown"
    m = re.search(r"(\d+)", bits[3]) if len(bits) > 3 else None
    return lang, persona, (int(m.group(1)) if m else 0)


def reasons_of(rj):
    rr = rj.get("rejection_reasons")
    if isinstance(rr, list):
        return [str(x) for x in rr if x]
    if isinstance(rr, dict):
        return [k for k, v in rr.items() if v]
    if isinstance(rr, str) and rr.strip():
        return [rr.strip()]
    return []


def put_if_new(cli, key, path, stats, dry):
    """Upload unless an object of the same size is already there."""
    size = os.path.getsize(path)
    try:
        head = cli.head_object(Bucket=BUCKET, Key=key)
        if head.get("ContentLength") == size:
            stats["skipped"] += 1
            return False
    except ClientError:
        pass
    if dry:
        stats["would_upload"] += 1
        stats["bytes"] += size
        return True
    cli.upload_file(path, BUCKET, key, ExtraArgs={"ContentType": "audio/wav"})
    stats["uploaded"] += 1
    stats["bytes"] += size
    return True


def put_bytes(cli, key, data, content_type, dry):
    if dry:
        return
    cli.put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only", help="one language only")
    args = ap.parse_args()

    if not BUCKET:
        sys.exit("  S3_BUCKET is not configured")

    cli = s3()
    stats = defaultdict(int)
    summary = []
    t0 = time.time()
    # A set can arrive as more than one task (a set split into "Conv 1-19" and
    # "Conv 20-30"), and those share a folder. Rows are gathered per folder and
    # written once at the end, so the later task cannot overwrite the earlier
    # task's manifest.
    rows_by_base = defaultdict(list)
    sheet_by_base = {}

    with app.app_context():
        tests = Test.query.filter_by(test_type="audio-segmentation").all()
        names = {r.id: (r.name or r.email or "") for r in Rater.query.all()}
        by_test = defaultdict(list)
        for r in Rating.query.all():
            by_test[r.test_id].append(r)

        for t in sorted(tests, key=lambda x: x.id):
            entries = t.json_entry if isinstance(t.json_entry, list) else []
            if not entries:
                continue
            lang, persona, setno = parts_of(t.description)
            if args.only and lang.lower() != args.only.lower():
                continue

            verdicts = {}
            for r in by_test.get(t.id, []):
                if not (r.page_no_progress and
                        r.completion_status in ("completed", "skipped")):
                    continue
                rj = r.results_json if isinstance(r.results_json, dict) else {}
                ev = str(rj.get("evaluation") or "").strip().lower()
                if ev in ("accept", "reject"):
                    verdicts[str(r.page_no_progress)] = (ev, rj, r)

            ids = {str((e or {}).get("id")) for e in entries}
            if ids - set(verdicts):
                stats["sets_skipped_incomplete"] += 1
                continue                      # still under review

            set_dir = str((entries[0] or {}).get("audio_filename", "")).split("/")[0]
            artist = "Unknown"
            try:
                with open(os.path.join(AUDIO_DIR, set_dir, "recorder.txt"),
                          encoding="utf-8") as fh:
                    artist = fh.read().strip() or "Unknown"
            except Exception:
                pass

            base = "%s/%s/%s/Set%d" % (ROOT, slug(lang), slug(persona), setno)
            rows = []
            n_acc = n_rej = 0

            for e in entries:
                eid = str((e or {}).get("id"))
                rel = (e or {}).get("audio_filename") or ""
                src = os.path.join(AUDIO_DIR, rel)
                if not os.path.isfile(src):
                    stats["clips_missing"] += 1
                    continue
                ev, rj, r = verdicts[eid]
                folder = "accepted" if ev == "accept" else "rejected"
                n_acc += 1 if ev == "accept" else 0
                n_rej += 1 if ev == "reject" else 0
                clip = os.path.basename(rel)
                key = "%s/%s/%s" % (base, folder, clip)
                put_if_new(cli, key, src, stats, args.dry_run)

                rows.append({
                    "clip_id": eid,
                    "verdict": "accepted" if ev == "accept" else "rejected",
                    "language": lang, "persona": persona, "set": setno,
                    "artist": artist,
                    "speaker": (e or {}).get("speaker") or "",
                    "role": (e or {}).get("role") or "",
                    "script": (e or {}).get("transcript") or "",
                    "rejection_reasons": ", ".join(reasons_of(rj)),
                    "notes": str(rj.get("notes") or rj.get("comment") or "").strip(),
                    "reviewer": names.get(r.rater_id, ""),
                    "reviewed_at": r.time_of_submission.isoformat()
                                   if r.time_of_submission else "",
                    "audio_path": "%s/%s" % (folder, clip),
                    "bytes": os.path.getsize(src),
                    "test_id": t.id,
                })

            rows_by_base[base].extend(rows)

            # the recording sheet, when the set folder still has it
            for x in os.listdir(os.path.join(AUDIO_DIR, set_dir)):
                if x.lower().endswith((".xlsx", ".xls")) and not x.startswith("~$"):
                    sheet_by_base.setdefault(
                        base, os.path.join(AUDIO_DIR, set_dir, x))
                    break

            stats["sets"] += 1
            summary.append((lang, persona, setno, artist, len(rows), n_acc, n_rej))
            print("  %-9s %-22s Set%-4s %-18s %4d clips (%d ok / %d rejected)"
                  % (lang, persona, setno, artist[:18], len(rows), n_acc, n_rej))

    # One manifest per folder, covering every task that contributed to it.
    for base, rows in sorted(rows_by_base.items()):
        rows.sort(key=lambda r: (r["verdict"], r["clip_id"]))
        jl = "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
        put_bytes(cli, base + "/manifest.jsonl", jl.encode("utf-8"),
                  "application/x-ndjson", args.dry_run)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
        put_bytes(cli, base + "/manifest.csv",
                  buf.getvalue().encode("utf-8-sig"), "text/csv", args.dry_run)
        stats["manifests"] += 1
    for base, path in sorted(sheet_by_base.items()):
        put_if_new(cli, "%s/%s" % (base, os.path.basename(path)), path,
                   stats, args.dry_run)

    # top-level docs
    if summary:
        lines = ["# QC backup\n",
                 "%d set(s), %d clip(s): %d accepted, %d rejected.\n"
                 % (stats["sets"], sum(s[4] for s in summary),
                    sum(s[5] for s in summary), sum(s[6] for s in summary)),
                 "\n| Language | Persona | Set | Artist | Clips | Accepted | Rejected |",
                 "|---|---|---|---:|---:|---:|---:|"]
        for lang, persona, setno, artist, n, a, j in sorted(summary):
            lines.append("| %s | %s | %d | %s | %d | %d | %d |"
                         % (lang, persona, setno, artist, n, a, j))
        put_bytes(cli, ROOT + "/SUMMARY.md", "\n".join(lines).encode("utf-8"),
                  "text/markdown", args.dry_run)
        put_bytes(cli, ROOT + "/README.md", README.encode("utf-8"),
                  "text/markdown", args.dry_run)

    print()
    print("  sets backed up        : %d" % stats["sets"])
    print("  sets skipped (ongoing): %d" % stats["sets_skipped_incomplete"])
    print("  clips uploaded        : %d" % stats["uploaded"])
    print("  clips already there   : %d" % stats["skipped"])
    if args.dry_run:
        print("  would upload          : %d" % stats["would_upload"])
    print("  bytes moved           : %.2f GB" % (stats["bytes"] / 1024.0 ** 3))
    print("  manifests written     : %d (one per folder)" % stats["manifests"])
    print("  clips missing on disk : %d" % stats["clips_missing"])
    print("  elapsed               : %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
