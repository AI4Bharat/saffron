#!/usr/bin/env python3
"""
admin_reports.py — admin dashboard reporting helpers.

1. artist_rejection_stats(): audio-segmentation QC rollup per VOICE ARTIST (the
   person who recorded the audio, read from <set_dir>/recorder.txt) — accept/reject
   counts, rejection rate, and the share of each rejection reason. Built to be
   handed straight to the vendor who supplies the artists.

2. tasks_export_rows(): flat table of tests (Sr. No. per language, Language,
   Task ID, Detail, No. of Tasks), optionally filtered by version, for CSV export.
"""
import csv
import io
import os
import re

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")

# The 31 reasons offered in AudioSegmentation.vue (keep in sync with availableReasons).
REJECTION_REASONS = [
    'incorrect_text', 'noise', 'mispronounce', 'weak_emotion',
    'incorrect_style', 'mismatch', 'skipping_words', 'not_normalized',
    'low_volume', 'noise_beginning', 'noise_end', 'wrong_speaker',
    'too_fast', 'fan', 'silence', 'unnatural', 'unclear',
    'wrong_language', 'duplicate', 'repeating_content', 'dramatic',
    'too_slow', 'page_flip', 'manual', 'flag', 'echo',
    'chatter', 'abnormal', 'objectionable_content', 'truncated_audio', 'others',
]


def reason_label(slug):
    return str(slug).replace('_', ' ').title()


def _set_dir_of(entries):
    if not entries:
        return ""
    return str(entries[0].get("audio_filename", "")).split("/")[0]


def _recorder_for(set_dir, _cache={}):
    """Voice artist for a set dir, from <set_dir>/recorder.txt ('Unknown' if absent)."""
    if set_dir in _cache:
        return _cache[set_dir]
    name = "Unknown"
    try:
        with open(os.path.join(AUDIO_DIR, set_dir, "recorder.txt"), encoding="utf-8") as fh:
            name = fh.read().strip() or "Unknown"
    except Exception:
        pass
    _cache[set_dir] = name
    return name


def _reasons_of(results_json):
    """Normalise rejection_reasons (list | dict | str) to a list of slugs."""
    rr = results_json.get("rejection_reasons")
    if isinstance(rr, list):
        return [str(x) for x in rr if x]
    if isinstance(rr, dict):
        return [str(k) for k, v in rr.items() if v]
    if rr:
        return [str(rr)]
    return []


def artist_rejection_stats(tests, ratings_by_test):
    """Per-artist QC rollup for audio-segmentation.

    tests            : iterable of Test rows
    ratings_by_test  : {test_id: [Rating, ...]}

    Returns {'artists': [...], 'overall': {...}} where each artist has:
      artist, batches, total, accepted, rejected, rejection_rate,
      reasons: [{reason, label, count, pct_of_rejections}]
    """
    per_artist = {}

    for test in tests:
        if test.test_type != "audio-segmentation":
            continue
        entries = test.json_entry if isinstance(test.json_entry, list) else []
        set_dir = _set_dir_of(entries)
        artist = _recorder_for(set_dir)
        language = (entries[0].get("language") if entries else None) or "Unknown"
        persona = (entries[0].get("persona") if entries else None) or "Unknown"

        a = per_artist.setdefault(artist, {
            "artist": artist, "batches": [], "total": 0, "accepted": 0,
            "rejected": 0, "_reasons": {},
        })
        b_total = b_acc = b_rej = 0

        for r in ratings_by_test.get(test.id, []):
            if not (r.page_no_progress and r.completion_status in ("completed", "skipped")):
                continue
            rj = r.results_json if isinstance(r.results_json, dict) else {}
            ev = str(rj.get("evaluation") or "").strip().lower()
            if ev == "accept":
                b_acc += 1
                b_total += 1
            elif ev == "reject":
                b_rej += 1
                b_total += 1
                for slug in _reasons_of(rj):
                    a["_reasons"][slug] = a["_reasons"].get(slug, 0) + 1

        if b_total:
            a["total"] += b_total
            a["accepted"] += b_acc
            a["rejected"] += b_rej
            a["batches"].append({
                "test_id": test.id,
                "description": test.description or "",
                "language": language,
                "persona": persona,
                "set_dir": set_dir,
                "total": b_total,
                "accepted": b_acc,
                "rejected": b_rej,
                "rejection_rate": round(100.0 * b_rej / b_total, 1),
            })

    artists = []
    overall_reasons = {}
    o_total = o_acc = o_rej = 0
    for a in per_artist.values():
        if not a["total"]:
            continue
        reasons = [
            {
                "reason": slug,
                "label": reason_label(slug),
                "count": cnt,
                # share of THIS artist's rejections that cite this reason
                "pct_of_rejections": round(100.0 * cnt / a["rejected"], 1) if a["rejected"] else 0.0,
            }
            for slug, cnt in a["_reasons"].items()
        ]
        reasons.sort(key=lambda x: -x["count"])
        for slug, cnt in a["_reasons"].items():
            overall_reasons[slug] = overall_reasons.get(slug, 0) + cnt
        o_total += a["total"]; o_acc += a["accepted"]; o_rej += a["rejected"]

        a["batches"].sort(key=lambda b: -b["rejection_rate"])
        artists.append({
            "artist": a["artist"],
            "total": a["total"],
            "accepted": a["accepted"],
            "rejected": a["rejected"],
            "rejection_rate": round(100.0 * a["rejected"] / a["total"], 1),
            "batch_count": len(a["batches"]),
            "batches": a["batches"],
            "reasons": reasons,
        })
    artists.sort(key=lambda x: -x["rejection_rate"])

    overall = {
        "total": o_total,
        "accepted": o_acc,
        "rejected": o_rej,
        "rejection_rate": round(100.0 * o_rej / o_total, 1) if o_total else 0.0,
        "reasons": sorted(
            [
                {
                    "reason": s, "label": reason_label(s), "count": c,
                    "pct_of_rejections": round(100.0 * c / o_rej, 1) if o_rej else 0.0,
                }
                for s, c in overall_reasons.items()
            ],
            key=lambda x: -x["count"],
        ),
    }
    return {"artists": artists, "overall": overall}


# ---------------------------------------------------------------------------
# Task export
# ---------------------------------------------------------------------------
_VERSION_RE = re.compile(r" - (version \d+|new version)", re.IGNORECASE)


def test_version(description):
    """'... - Version 6 - Part 1' -> 'Version 6'; 'New Version'; else 'Base'."""
    m = _VERSION_RE.search(description or "")
    return m.group(1).title() if m else "Base"


def test_language(description):
    """'Conversation Editable - Hindi - ...' -> 'Hindi'."""
    parts = [p.strip() for p in (description or "").split(" - ")]
    return parts[1] if len(parts) > 1 else "Unknown"


def tasks_export_rows(tests, test_type=None, version=None):
    """Rows for the export table, Sr. No. restarting per language.

    Returns (rows, headers). version may be '6', 'Version 6', 'new', 'base' or None.
    """
    want_v = None
    if version:
        v = str(version).strip().lower()
        if v in ("new", "new version"):
            want_v = "New Version"
        elif v in ("base", "none"):
            want_v = "Base"
        else:
            want_v = f"Version {re.sub(r'[^0-9]', '', v)}"

    picked = []
    for t in tests:
        if test_type and t.test_type != test_type:
            continue
        desc = t.description or ""
        if want_v and test_version(desc) != want_v:
            continue
        n = len(t.json_entry) if isinstance(t.json_entry, list) else 0
        picked.append((test_language(desc), t.id, desc, n))

    # group by language, keep test-id order inside a language
    picked.sort(key=lambda r: (r[0], r[1]))
    rows, counters = [], {}
    for lang, tid, desc, n in picked:
        counters[lang] = counters.get(lang, 0) + 1
        rows.append({
            "sr_no": counters[lang],
            "language": lang,
            "task_id": f"#{tid}",
            "detail": desc,
            "num_tasks": n,
        })
    headers = ["Sr. No.", "Language", "Task ID", "Detail", "No. of Task"]
    return rows, headers


def tasks_export_csv(tests, test_type=None, version=None):
    rows, headers = tasks_export_rows(tests, test_type, version)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(headers)
    for r in rows:
        w.writerow([r["sr_no"], r["language"], r["task_id"], r["detail"], r["num_tasks"]])
    return buf.getvalue()


def artist_report_csv(stats):
    """Vendor-shareable CSV: per-artist rates, then per-artist reason breakdown."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Artist", "Batches", "Total Reviewed", "Accepted", "Rejected", "Rejection Rate %"])
    for a in stats["artists"]:
        w.writerow([a["artist"], a["batch_count"], a["total"], a["accepted"],
                    a["rejected"], a["rejection_rate"]])
    o = stats["overall"]
    w.writerow(["OVERALL", "", o["total"], o["accepted"], o["rejected"], o["rejection_rate"]])
    w.writerow([])
    w.writerow(["Artist", "Rejection Reason", "Count", "% of that artist's rejections"])
    for a in stats["artists"]:
        for r in a["reasons"]:
            w.writerow([a["artist"], r["label"], r["count"], r["pct_of_rejections"]])
    w.writerow([])
    w.writerow(["OVERALL", "Rejection Reason", "Count", "% of all rejections"])
    for r in o["reasons"]:
        w.writerow(["", r["label"], r["count"], r["pct_of_rejections"]])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Clip-level audio-segmentation export (with playable Saffron links)
# ---------------------------------------------------------------------------
# Public base URL of the app; a link opens the exact task so the audio can be played.
SAFFRON_BASE_URL = os.environ.get("SAFFRON_BASE_URL", "https://tts-saffron.ai4bharat.org")


def task_link(test_id, task_id):
    """Deep link that opens <test_id> scrolled/jumped to <task_id> (TestView reads ?task=)."""
    return f"{SAFFRON_BASE_URL}/{test_id}?task={task_id}"


def audio_clips_rows(tests, ratings_by_test, only_rejected=True):
    """One row per reviewed audio clip: who recorded it, the verdict, why, and a link
    that opens the clip in Saffron so the vendor can listen to it."""
    rows = []
    for test in tests:
        if test.test_type != "audio-segmentation":
            continue
        entries = test.json_entry if isinstance(test.json_entry, list) else []
        by_id = {str(it.get("id")): it for it in entries}
        set_dir = _set_dir_of(entries)
        artist = _recorder_for(set_dir)
        language = (entries[0].get("language") if entries else None) or ""
        persona = (entries[0].get("persona") if entries else None) or ""
        # excel set label, e.g. 'Set2' -- from the description tail
        set_label = ""
        parts = [p.strip() for p in (test.description or "").split(" - ")]
        if len(parts) >= 4:
            set_label = parts[3]

        for r in ratings_by_test.get(test.id, []):
            if not (r.page_no_progress and r.completion_status in ("completed", "skipped")):
                continue
            rj = r.results_json if isinstance(r.results_json, dict) else {}
            ev = str(rj.get("evaluation") or "").strip().lower()
            if only_rejected and ev != "reject":
                continue
            task_id = str(rj.get("id") or r.page_no_progress or "")
            item = by_id.get(task_id, {})
            reasons = [reason_label(x) for x in _reasons_of(rj)]
            rows.append({
                "artist": artist,
                "language": language,
                "persona": persona,
                "set": set_label,
                "test_id": test.id,
                "task_id": task_id,
                "speaker": item.get("speaker", ""),
                "evaluation": ev,
                "rejection_reasons": "; ".join(reasons),
                "custom_reason": rj.get("custom_rejection_reason") or "",
                "annotator": rj.get("rater_email") or "",
                "transcript": (item.get("transcript") or "")[:400],
                "link": task_link(test.id, task_id),
            })
    rows.sort(key=lambda x: (x["artist"], x["set"], x["task_id"]))
    return rows


def audio_clips_csv(tests, ratings_by_test, only_rejected=True):
    rows = audio_clips_rows(tests, ratings_by_test, only_rejected)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["Artist", "Language", "Persona", "Set", "Test ID", "Task ID", "Speaker",
                "Evaluation", "Rejection Reasons", "Custom Reason", "Annotator",
                "Transcript", "Listen (Saffron link)"])
    for r in rows:
        w.writerow([r["artist"], r["language"], r["persona"], r["set"], r["test_id"],
                    r["task_id"], r["speaker"], r["evaluation"], r["rejection_reasons"],
                    r["custom_reason"], r["annotator"], r["transcript"], r["link"]])
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Annotator export (Current working task, pending tasks, tasks done)
# ---------------------------------------------------------------------------
def annotators_export_rows(raters, tests, ratings_by_rater, d_from=None, d_to=None, rater_id=None):
    """Generates rows summarizing annotator work, status, assigned/pending tasks,
    current task working on, and total completed tasks count.

    d_from, d_to: optional datetime objects for date range filtering.
    rater_id: optional integer to filter for a single specific rater.
    """
    if rater_id is not None:
        raters = [r for r in raters if r.id == rater_id]

    tests_by_id = {t.id: t for t in tests}
    rows = []

    for rater in raters:
        assigned_ids = [int(x.strip()) for x in (rater.assigned_tasks or "").split(",") if x.strip().isdigit()]
        all_rater_ratings = ratings_by_rater.get(rater.id, [])

        # Filter ratings by date range if specified
        filtered_ratings = []
        for r in all_rater_ratings:
            if d_from and r.time_of_submission and r.time_of_submission < d_from:
                continue
            if d_to and r.time_of_submission and r.time_of_submission >= d_to:
                continue
            filtered_ratings.append(r)

        # Unique completed items across lifetime & period
        completed_task_ids = {
            str(r.page_no_progress) for r in filtered_ratings
            if r.page_no_progress and r.completion_status in ("completed", "skipped")
        }
        completed_count = len(completed_task_ids)
        submissions_count = len(filtered_ratings)

        total_secs = 0.0
        last_active_dt = None
        for r in filtered_ratings:
            if r.time_taken_to_submit:
                secs = r.time_taken_to_submit / 1000.0
                if 0 < secs < 7200:
                    total_secs += secs
            if r.time_of_submission and (last_active_dt is None or r.time_of_submission > last_active_dt):
                last_active_dt = r.time_of_submission

        # Completed item IDs per test_id for lifetime progress tracking
        completed_by_test = {}
        for r in all_rater_ratings:
            if r.page_no_progress and r.completion_status in ("completed", "skipped"):
                completed_by_test.setdefault(r.test_id, set()).add(str(r.page_no_progress))

        total_assigned_tasks = 0
        pending_batch_ids = []
        working_on_desc = None

        for tid in assigned_ids:
            test = tests_by_id.get(tid)
            if not test:
                continue
            entries = test.json_entry if isinstance(test.json_entry, list) else []
            num_items = len(entries)
            total_assigned_tasks += num_items

            comp_items = completed_by_test.get(tid, set())
            if len(comp_items) < num_items:
                pending_batch_ids.append(tid)
                if working_on_desc is None:
                    # Determine next pending item task ID
                    next_item_id = None
                    for idx, item in enumerate(entries):
                        item_id = str(item.get("id") if isinstance(item, dict) and "id" in item else (idx + 1))
                        if item_id not in comp_items:
                            next_item_id = item_id
                            break
                    if next_item_id:
                        working_on_desc = f"Test #{tid} (Task: {next_item_id})"
                    else:
                        working_on_desc = f"Test #{tid}"

        account_active = bool(getattr(rater, "is_active", True))
        account_status = "Active" if account_active else "Deactivated"

        if not assigned_ids:
            status_text = "Unassigned"
            working_on_str = "None (Unassigned)"
        elif not pending_batch_ids:
            status_text = "Completed"
            working_on_str = "None (All Completed)"
        elif completed_count > 0:
            status_text = "In Progress"
            working_on_str = working_on_desc or f"Test #{pending_batch_ids[0]}"
        else:
            status_text = "Not Started"
            working_on_str = working_on_desc or f"Test #{pending_batch_ids[0]}"

        # Calculate exact pending tasks count
        assigned_completed_count = sum(
            len(completed_by_test.get(tid, set())) for tid in assigned_ids
        )
        pending_tasks_count = max(0, total_assigned_tasks - assigned_completed_count)

        rows.append({
            "rater_id": rater.id,
            "name": rater.name,
            "email": rater.email,
            "gender": rater.gender or "",
            "age": rater.age or "",
            "account_status": account_status,
            "status": status_text,
            "assigned_batches": ", ".join(f"#{x}" for x in assigned_ids) if assigned_ids else "None",
            "total_assigned_tasks": total_assigned_tasks,
            "tasks_completed": completed_count,
            "pending_tasks_count": pending_tasks_count,
            "current_working_task": working_on_str,
            "pending_batch_ids": ", ".join(f"#{x}" for x in pending_batch_ids) if pending_batch_ids else "None",
            "submissions": submissions_count,
            "hours_spent": round(total_secs / 3600.0, 2),
            "last_active": last_active_dt.isoformat() if last_active_dt else "",
        })

    rows.sort(key=lambda x: -x["tasks_completed"])
    return rows


def annotators_export_csv(raters, tests, ratings_by_rater, d_from=None, d_to=None, rater_id=None):
    rows = annotators_export_rows(raters, tests, ratings_by_rater, d_from=d_from, d_to=d_to, rater_id=rater_id)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Annotator ID", "Name", "Email", "Gender", "Age", "Account Status", "Status",
        "Assigned Test Batches", "Total Tasks Assigned", "Tasks Done (Completed)",
        "Pending Tasks Count", "Current Working Task / Batch", "Pending Batch IDs",
        "Total Submissions", "Hours Spent", "Last Active Date"
    ])
    for r in rows:
        w.writerow([
            r["rater_id"], r["name"], r["email"], r["gender"], r["age"],
            r["account_status"], r["status"], r["assigned_batches"],
            r["total_assigned_tasks"], r["tasks_completed"], r["pending_tasks_count"],
            r["current_working_task"], r["pending_batch_ids"], r["submissions"],
            r["hours_spent"], r["last_active"]
        ])
    return buf.getvalue()


def rater_detailed_ratings_csv(rater, tests, ratings):
    """CSV export of all detailed rating submissions for a specific annotator."""
    tests_by_id = {t.id: t for t in tests}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Rating ID", "Annotator ID", "Annotator Name", "Annotator Email",
        "Test ID", "Test Type", "Test Description", "Task / Item ID",
        "Completion Status", "Submission Time", "Time Taken (sec)", "Results / Evaluation Summary"
    ])
    for r in ratings:
        t = tests_by_id.get(r.test_id)
        desc = t.description if t else ""
        ttype = t.test_type if t else ""

        rj = r.results_json if isinstance(r.results_json, dict) else {}
        summary_parts = []
        if "evaluation" in rj:
            summary_parts.append(f"Eval: {rj.get('evaluation')}")
        if "rejection_reasons" in rj:
            reasons = _reasons_of(rj)
            if reasons:
                summary_parts.append(f"Reasons: {'; '.join(reasons)}")
        if "custom_rejection_reason" in rj and rj.get("custom_rejection_reason"):
            summary_parts.append(f"Custom: {rj.get('custom_rejection_reason')}")
        if "transcript" in rj and rj.get("transcript"):
            summary_parts.append(f"Transcript: {str(rj.get('transcript'))[:100]}")
        summary_str = " | ".join(summary_parts) if summary_parts else (str(rj)[:150] if rj else "")

        w.writerow([
            r.id, rater.id, rater.name, rater.email,
            r.test_id, ttype, desc, r.page_no_progress or "",
            r.completion_status or "",
            r.time_of_submission.isoformat() if r.time_of_submission else "",
            round((r.time_taken_to_submit or 0.0) / 1000.0, 1),
            summary_str
        ])
    return buf.getvalue()


def all_detailed_ratings_csv(raters, tests, ratings):
    """CSV export of all detailed rating submissions across all annotators."""
    raters_by_id = {r.id: r for r in raters}
    tests_by_id = {t.id: t for t in tests}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Rating ID", "Annotator ID", "Annotator Name", "Annotator Email",
        "Test ID", "Test Type", "Test Description", "Task / Item ID",
        "Completion Status", "Submission Time", "Time Taken (sec)", "Results / Evaluation Summary"
    ])
    for r in ratings:
        rater = raters_by_id.get(r.rater_id)
        r_name = rater.name if rater else f"Rater #{r.rater_id}"
        r_email = rater.email if rater else ""
        t = tests_by_id.get(r.test_id)
        desc = t.description if t else ""
        ttype = t.test_type if t else ""

        rj = r.results_json if isinstance(r.results_json, dict) else {}
        summary_parts = []
        if "evaluation" in rj:
            summary_parts.append(f"Eval: {rj.get('evaluation')}")
        if "rejection_reasons" in rj:
            reasons = _reasons_of(rj)
            if reasons:
                summary_parts.append(f"Reasons: {'; '.join(reasons)}")
        if "custom_rejection_reason" in rj and rj.get("custom_rejection_reason"):
            summary_parts.append(f"Custom: {rj.get('custom_rejection_reason')}")
        if "transcript" in rj and rj.get("transcript"):
            summary_parts.append(f"Transcript: {str(rj.get('transcript'))[:100]}")
        summary_str = " | ".join(summary_parts) if summary_parts else (str(rj)[:150] if rj else "")

        w.writerow([
            r.id, r.rater_id, r_name, r_email,
            r.test_id, ttype, desc, r.page_no_progress or "",
            r.completion_status or "",
            r.time_of_submission.isoformat() if r.time_of_submission else "",
            round((r.time_taken_to_submit or 0.0) / 1000.0, 1),
            summary_str
        ])
    return buf.getvalue()



