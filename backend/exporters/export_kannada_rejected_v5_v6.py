"""Export REJECTED Kannada conversation-editable annotations (Version 5 + Version 6)
to a JSONL file, one line per rejected conversation.

  --comments with     only rejections that carry an annotator comment
  --comments without  only rejections with a blank/missing comment
  --comments all      every rejection (default)

Standalone: talks to instance/database.db via sqlite3, no Flask app context needed.
Merge logic mirrors exporters/export_conversations.py.
"""
import argparse
import json
import os
import re
import sqlite3
import sys

DB_PATH = "/root/saffron/backend/instance/database.db"
EXPORT_DIR = "/root/saffron/backend/exports"

VERSION_RE = re.compile(r"Version (\d+)")
PART_RE = re.compile(r"Part (\d+)")

DROP_TURN_KEYS = {"english", "english_text", "original", "original_text", "en", "text_en"}


def load_tests(conn):
    rows = conn.execute(
        """
        SELECT id, description, test_type, language_hint
        FROM test
        WHERE test_type = 'conversation-editable'
          AND language_hint = 'kannada'
          AND (description LIKE '%Version 5%' OR description LIKE '%Version 6%')
        ORDER BY id
        """
    ).fetchall()
    return rows


def parse_desc(desc):
    """'Conversation Editable - Kannada - Calm Explainer - Elementary - Version 6 - Part 2 (...)'"""
    parts = [p.strip() for p in desc.split(" - ")]
    persona = parts[2] if len(parts) > 2 else None
    grade = parts[3] if len(parts) > 3 else None
    v = VERSION_RE.search(desc)
    p = PART_RE.search(desc)
    return {
        "persona": persona,
        "grade_bucket": grade,
        "version": int(v.group(1)) if v else None,
        "part": int(p.group(1)) if p else None,
    }


def clean_turn(turn):
    return {k: v for k, v in turn.items() if k not in DROP_TURN_KEYS}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--comments", choices=["with", "without", "all"], default="all",
                    help="filter rejections by presence of an annotator comment")
    ap.add_argument("--out", default=None, help="output path (default derived from --comments)")
    args = ap.parse_args()

    suffix = {"with": "_with_comments", "without": "_without_comments", "all": ""}[args.comments]
    out_path = args.out or os.path.join(
        EXPORT_DIR, "kannada_rejected%s_v5_v6.jsonl" % suffix)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    tests = load_tests(conn)
    if not tests:
        print("No matching tests found.", file=sys.stderr)
        sys.exit(1)

    raters = {r["id"]: r for r in conn.execute("SELECT id, name, email FROM rater")}

    out_records = []
    per_test_counts = {}

    for t in tests:
        test_id = t["id"]
        meta = parse_desc(t["description"] or "")

        originals = {}
        try:
            items = json.loads(
                conn.execute("SELECT json_entry FROM test WHERE id = ?", (test_id,)).fetchone()[0]
            )
        except (TypeError, ValueError):
            items = []
        for it in items or []:
            if isinstance(it, dict) and it.get("id") is not None:
                originals[str(it["id"])] = it

        ratings = conn.execute(
            """
            SELECT id, rater_id, test_id, results_json, time_of_submission,
                   time_taken_to_submit, page_no_progress, completion_status, verdict
            FROM rating
            WHERE test_id = ? AND completion_status = 'completed'
            ORDER BY time_of_submission
            """,
            (test_id,),
        ).fetchall()

        # keep only the latest submission per conversation item
        latest = {}
        for r in ratings:
            try:
                data = json.loads(r["results_json"])
            except (TypeError, ValueError):
                continue
            if not isinstance(data, dict):
                continue
            item_id = r["page_no_progress"] or data.get("id")
            if item_id is None:
                continue
            key = str(item_id)
            prev = latest.get(key)
            if prev is None or (r["time_of_submission"] or "") >= (prev[0]["time_of_submission"] or ""):
                latest[key] = (r, data)

        n = 0
        for key, (r, data) in latest.items():
            evaluation = data.get("evaluation") or r["verdict"]
            if evaluation != "reject":
                continue
            comments = (data.get("comments") or "").strip()
            if args.comments == "with" and not comments:
                continue
            if args.comments == "without" and comments:
                continue

            orig = originals.get(key, {})
            rec = json.loads(json.dumps(orig)) if orig else {"id": key}

            # merge annotator's submitted version over the original
            for scene in ("pre_scene", "post_scene"):
                if scene in data:
                    if orig.get(scene) is not None and data[scene] != orig.get(scene):
                        rec["original_" + scene] = orig[scene]
                    rec[scene] = data[scene]

            orig_key = next(
                (k for k in ("dialogue", "conversation", "turns")
                 if isinstance(rec.get(k), list)), None
            )
            rated_key = next(
                (k for k in ("dialogue", "conversation", "turns")
                 if isinstance(data.get(k), list)), None
            )
            if orig_key and rated_key:
                orig_turns = [clean_turn(x) for x in rec[orig_key]]
                merged = json.loads(json.dumps(orig_turns))
                rated_turns = data[rated_key]
                for i, turn in enumerate(merged):
                    if i < len(rated_turns):
                        for k, v in rated_turns[i].items():
                            if k not in DROP_TURN_KEYS and k != "speaker":
                                turn[k] = v
                if merged != orig_turns:
                    rec["original_" + orig_key] = orig_turns
                rec[orig_key] = merged
            elif rated_key:
                rec[rated_key] = [clean_turn(x) for x in data[rated_key]]

            for junk in ("pre_scene_en", "post_scene_en", "misconception_text_en"):
                rec.pop(junk, None)

            rec["evaluation"] = "reject"
            rec["comments"] = comments

            rater = raters.get(r["rater_id"])
            rec["annotation"] = {
                "test_id": test_id,
                "test_description": t["description"],
                "version": meta["version"],
                "part": meta["part"],
                "teacher_persona_label": meta["persona"],
                "grade_bucket_label": meta["grade_bucket"],
                "language": "kannada",
                "rating_id": r["id"],
                "rater_id": r["rater_id"],
                "rater_name": rater["name"] if rater else None,
                "rater_email": rater["email"] if rater else None,
                "submitted_at": r["time_of_submission"],
                "time_taken_seconds": r["time_taken_to_submit"],
                "has_comments": bool(comments),
            }

            out_records.append(rec)
            n += 1

        if n:
            per_test_counts[test_id] = (t["description"], n)

    out_records.sort(key=lambda x: (x["annotation"]["version"] or 0,
                                    x["annotation"]["test_id"],
                                    x["annotation"]["rating_id"]))

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for rec in out_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"Scanned {len(tests)} Kannada conversation-editable tests (Version 5 + 6)")
    print(f"Filter: rejected, comments={args.comments}")
    for tid, (desc, n) in sorted(per_test_counts.items()):
        print(f"  {tid}  {n:>2} rejected   {desc}")
    v5 = sum(1 for r in out_records if r["annotation"]["version"] == 5)
    v6 = sum(1 for r in out_records if r["annotation"]["version"] == 6)
    print(f"\nMatched: {len(out_records)}  (Version 5: {v5}, Version 6: {v6})")
    print(f"Written to: {out_path}")


if __name__ == "__main__":
    main()
