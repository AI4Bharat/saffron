#!/usr/bin/env python3
"""Every accepted conversation, as JSONL, arranged language then persona.

    <Language>/<Persona>_accepted.jsonl
    <Language>/<Persona>_accepted_with_comments.jsonl
    MANIFEST.json
    README.md

An item counts as accepted when its most recent completed rating says 'accept'.
The annotator's corrections are merged in, so what comes out is the script as
approved -- pre-scene, post-scene and the dialogue turns as edited, not the
generated original. Both conversation task types are included.

    python export_all_conversations.py --out /data2/all_conversation
    python export_all_conversations.py --out ... --dry-run
"""
import argparse
import os
os.environ["SAFFRON_SKIP_BOOT_MIGRATIONS"] = "1"
import json
import re
import sys
from collections import defaultdict

sys.path.insert(0, "/root/saffron/backend")

from main import app
from application.models import Test, Rating

TASK_TYPES = ("conversation-editable", "conversation-evaluation")
CONV_KEYS = ("dialogue", "conversation", "turns")

README = """# Accepted conversations

Every conversation an annotator accepted, across both conversation task types
and every version, as JSONL.

## Layout

    <Language>/<Persona>_accepted.jsonl                every clean accept
    <Language>/<Persona>_accepted_with_comments.jsonl  accepts carrying a note
    MANIFEST.json                  every file, its count and its version split
    README.md                      this file

One JSON object per line. A line is a whole conversation.

## What a row contains

The item as it was generated, with the annotator's corrections merged over it,
plus:

| field | meaning |
|---|---|
| `evaluation` | always `accept` here -- rejected items are not exported |
| `comments` | what the annotator wrote, when they wrote anything |
| `pre_scene`, `post_scene` | the accepted version, corrected where edited |
| `dialogue` | the turns as accepted, with the annotator's text |
| `_source` | which test, language, persona and version the row came from |

`dialogue` is the corrected script. The generated original is not kept
separately -- if a turn was edited, the edited text is what an annotator
approved and what should be recorded.

Only accepted items are here. Rejected and unreviewed ones are left out.
"""


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", (s or "").strip()).strip("_") or "Unknown"


PERSONAS = ("calm_explainer", "energetic_enthusiast", "reflective_mentor",
            "relatable_peer", "socratic_challenger", "storyteller",
            "strict_disciplinarian", "warm_encourager")


def parts_of(desc):
    """'Conversation Editable - Marathi - Storyteller - Middle - Version 5 - Part 1'.

    The persona slot is not always a persona: the re-review batches are titled
    'Accepted With Comments' and hold several personas at once, so only a value
    that is actually a known persona is trusted. Otherwise the item decides.
    """
    bits = [b.strip() for b in (desc or "").split(" - ")]
    lang = bits[1] if len(bits) > 1 else "Unknown"
    said = bits[2] if len(bits) > 2 else ""
    persona = said if said.lower().replace(" ", "_") in PERSONAS else None
    m = re.search(r"Version\s+([0-9]+|New)", desc or "", re.I)
    version = ("Version_%s" % m.group(1)) if m else "Base"
    return lang, persona, version


def persona_of(item, from_desc):
    """The conversation's own persona, preferred over whatever the title said."""
    own = (item.get("teacher_persona") or item.get("persona") or "").strip()
    if own:
        return own.replace("_", " ").title()
    if from_desc:
        return from_desc
    return "Unknown"


def merge(item, rating_data):
    """The item with the annotator's corrections applied, as the exporter does."""
    out = json.loads(json.dumps(item))
    out["evaluation"] = rating_data.get("evaluation")
    out["comments"] = rating_data.get("comments")
    for key in ("pre_scene", "post_scene"):
        if key in rating_data:
            out[key] = rating_data[key]

    orig_key = next((k for k in CONV_KEYS
                     if isinstance(out.get(k), list)), None)
    rated_key = next((k for k in CONV_KEYS
                      if isinstance(rating_data.get(k), list)), None)
    if orig_key and rated_key:
        rated = rating_data[rated_key]
        for i, turn in enumerate(out[orig_key]):
            if i < len(rated) and isinstance(rated[i], dict) and isinstance(turn, dict):
                for k, v in rated[i].items():
                    turn[k] = v
    return out


def version_rank(label):
    """Order the review rounds: Base first, then Version_2 .. Version_10."""
    m = re.search(r"(\d+)", str(label or ""))
    if m:
        return int(m.group(1))
    return 1 if str(label).lower().startswith("new") else 0


def latest_only(rows):
    """One row per conversation: the newest round that judged it."""
    best = {}
    for r in rows:
        key = str(r.get("id"))
        rank = version_rank((r.get("_source") or {}).get("version"))
        if key not in best or rank > best[key][0]:
            best[key] = (rank, r)
    return [v[1] for v in best.values()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--exclude-versions", default="",
                    help="Comma-separated rounds to leave out, e.g. 10 or Version_10")
    args = ap.parse_args()
    skip_versions = {version_rank(v) for v in
                     args.exclude_versions.split(',') if v.strip()}
    if skip_versions:
        print('  leaving out round(s): %s' % sorted(skip_versions))

    with app.app_context():
        tests = [t for t in Test.query.filter(
            Test.test_type.in_(TASK_TYPES)).all()]
        print("  conversation tests: %d" % len(tests))

        by_test = defaultdict(list)
        for r in Rating.query.filter(
                Rating.completion_status.in_(["completed", "skipped"])).yield_per(5000):
            by_test[r.test_id].append(r)
        print("  tests with ratings: %d" % len(by_test))

        # (language, persona, version) -> rows
        buckets = defaultdict(list)
        seen_ids = set()
        stats = defaultdict(int)

        for t in tests:
            items = t.json_entry if isinstance(t.json_entry, list) else []
            if not items:
                continue
            lang, persona, version = parts_of(t.description)

            latest = {}
            for r in by_test.get(t.id, []):
                key = r.page_no_progress
                if key is None and isinstance(r.results_json, dict):
                    key = r.results_json.get("id")
                if key is None:
                    continue
                key = str(key)
                prev = latest.get(key)
                if prev is None or (r.time_of_submission and prev.time_of_submission
                                    and r.time_of_submission > prev.time_of_submission):
                    latest[key] = r

            for item in items:
                stats["items seen"] += 1
                iid = str(item.get("id"))
                r = latest.get(iid)
                if r is None:
                    stats["never reviewed"] += 1
                    continue
                data = r.results_json if isinstance(r.results_json, dict) else {}
                if (data.get("evaluation") or "").strip().lower() != "accept":
                    stats["not accepted"] += 1
                    continue
                # A conversation legitimately appears in more than one round --
                # its original version and a later re-review -- and both were
                # accepted, so both are kept. Only a repeat WITHIN one
                # (language, persona, version) is a true duplicate.
                persona_here = persona_of(item, persona)
                dedupe_key = (lang, persona_here, version, iid)
                if dedupe_key in seen_ids:
                    stats["duplicate within a version"] += 1
                    continue
                seen_ids.add(dedupe_key)

                row = merge(item, data)
                row["_source"] = {
                    "test_id": t.id, "test_type": t.test_type,
                    "description": t.description, "language": lang,
                    "persona": persona_here, "version": version,
                    "accepted_at": (r.time_of_submission.isoformat()
                                    if r.time_of_submission else None),
                }
                if version_rank(version) in skip_versions:
                    stats["left out by --exclude-versions"] += 1
                    continue
                buckets[(lang, persona_here, version)].append(row)
                stats["accepted"] += 1

    print()
    for k in ("items seen", "accepted", "not accepted", "never reviewed",
              "duplicate within a version", "left out by --exclude-versions"):
        print("  %-16s %d" % (k, stats[k]))

    per_lang = defaultdict(int)
    for (lang, _p, _v), rows in buckets.items():
        per_lang[lang] += len(rows)
    print()
    print("  accepted per language:")
    for lang, n in sorted(per_lang.items()):
        print("     %-10s %d" % (lang, n))

    if args.dry_run:
        print("\n  --dry-run: nothing written.")
        return 0

    # One file per language and persona: every accepted conversation for that
    # pair, whichever round it came from. The version stays on each row in
    # _source, so nothing is lost by not splitting the files.
    merged = defaultdict(list)
    for (lang, persona, version), rows in buckets.items():
        merged[(lang, persona)].extend(rows)

    manifest = []
    written = 0
    per_persona = defaultdict(lambda: defaultdict(int))
    for (lang, persona), rows in sorted(merged.items()):
        rows.sort(key=lambda r: ((r.get("_source") or {}).get("version", ""),
                                 str(r.get("id", ""))))
        for r in rows:
            per_persona[(lang, persona)][(r.get("_source") or {}).get("version", "?")] += 1
        d = os.path.join(args.out, slug(lang))
        os.makedirs(d, exist_ok=True)

        # A comment means the annotator accepted the conversation but wanted
        # a change, so it is not ready to record as written. Keep them apart.
        # A later round supersedes an earlier one: a conversation fixed and
        # re-accepted must not still be listed as needing that fix.
        rows = latest_only(rows)
        clean = [r for r in rows if not str(r.get("comments") or "").strip()]
        noted = [r for r in rows if str(r.get("comments") or "").strip()]

        for kind, subset in (("accepted", clean),
                             ("accepted_with_comments", noted)):
            name = "%s_%s.jsonl" % (slug(persona), kind)
            path = os.path.join(d, name)
            with open(path, "w", encoding="utf-8") as fh:
                for row in subset:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
            manifest.append({
                "language": lang, "persona": persona, "kind": kind,
                "file": os.path.relpath(path, args.out).replace(os.sep, "/"),
                "conversations": len(subset),
                "by_version": (dict(per_persona[(lang, persona)])
                               if kind == "accepted" else {}),
                "bytes": os.path.getsize(path),
            })
            print("     %-64s %5d conversation(s)"
                  % (os.path.relpath(path, args.out), len(subset)))


    with open(os.path.join(args.out, "MANIFEST.json"), "w", encoding="utf-8") as fh:
        json.dump({"generated_from": "saffron conversation tasks",
                   "task_types": list(TASK_TYPES),
                   "conversations": sum(m["conversations"] for m in manifest),
                   "files": manifest}, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(args.out, "README.md"), "w", encoding="utf-8") as fh:
        fh.write(README)

    print()
    print("  %d file(s), %d conversation(s) -> %s"
          % (written, sum(m["conversations"] for m in manifest), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
