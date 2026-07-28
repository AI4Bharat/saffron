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

# The 31 reasons currently OFFERED in AudioSegmentation.vue — keep in sync with its
# `availableReasons`. Anything an old submission stores that is not in here counts as
# RETIRED: it can no longer be picked, so the admin dashboard flags those clips for
# re-review instead of letting a dead reason sit in the reports unnoticed.
REJECTION_REASONS = [
    'abnormal', 'artist_issue', 'chatter', 'dramatic',
    'duplicate', 'echo', 'fan', 'flag',
    'incorrect_style', 'incorrect_text', 'low_volume', 'manual',
    'mispronounce', 'mismatch', 'noise', 'noise_beginning',
    'noise_end', 'not_normalized', 'objectionable_content', 'page_flip',
    'repeating_content', 'silence', 'skipping_words', 'too_fast',
    'too_slow', 'truncated_audio', 'unclear', 'unnatural',
    'weak_emotion', 'wrong_language', 'wrong_speaker',
]
ACTIVE_REASONS = frozenset(REJECTION_REASONS)


def retired_reasons_of(results_json):
    """Stored rejection reasons that the UI no longer offers (e.g. the old 'others')."""
    return [s for s in _reasons_of(results_json) if s not in ACTIVE_REASONS]


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


def _batch_language(entries):
    """Language of a batch: the most common 'language' across its items."""
    counts = {}
    for item in entries or []:
        lang = (item or {}).get("language") if isinstance(item, dict) else None
        if lang:
            counts[lang] = counts.get(lang, 0) + 1
    return max(counts, key=counts.get) if counts else "Unknown"


def _empty_bucket():
    return {"clips": 0, "total": 0, "accepted": 0, "rejected": 0,
            "pending": 0, "batch_count": 0, "_reasons": {}}


def _merge_bucket(dst, src):
    for k in ("clips", "total", "accepted", "rejected", "pending", "batch_count"):
        dst[k] += src[k]
    for slug, cnt in src["_reasons"].items():
        dst["_reasons"][slug] = dst["_reasons"].get(slug, 0) + cnt


def _finish_bucket(b):
    """Turn an accumulator into the public shape (rates + sorted reasons)."""
    reasons = sorted(
        [
            {
                "reason": slug,
                "label": reason_label(slug),
                "count": cnt,
                # share of THIS bucket's rejections that cite the reason
                "pct_of_rejections": round(100.0 * cnt / b["rejected"], 1) if b["rejected"] else 0.0,
            }
            for slug, cnt in b["_reasons"].items()
        ],
        key=lambda x: -x["count"],
    )
    return {
        "clips": b["clips"],
        "total": b["total"],
        "accepted": b["accepted"],
        "rejected": b["rejected"],
        "pending": b["pending"],
        "batch_count": b["batch_count"],
        "rejection_rate": round(100.0 * b["rejected"] / b["total"], 1) if b["total"] else 0.0,
        "pending_rate": round(100.0 * b["pending"] / b["clips"], 1) if b["clips"] else 0.0,
        "reviewed_rate": round(100.0 * (b["clips"] - b["pending"]) / b["clips"], 1) if b["clips"] else 0.0,
        "reasons": reasons,
    }


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


def artist_rejection_stats(tests, ratings_by_test, language=None):
    """Per-artist QC rollup for audio-segmentation.

    tests            : iterable of Test rows
    ratings_by_test  : {test_id: [Rating, ...]}
    language         : keep only batches of this language (None = every language)

    Returns {'artists': [...], 'overall': {...}, 'languages': [...]} where each
    artist has:
      artist, batches, clips, total, accepted, rejected, pending, rejection_rate,
      reasons: [{reason, label, count, pct_of_rejections}],
      by_language: {lang: {clips, total, accepted, rejected, pending,
                           rejection_rate, reasons: [...]}}

    'total' stays the number of REVIEWED clips (accepted + rejected) so existing
    consumers keep working; 'clips' is everything in the artist's batches and
    'pending' is what nobody has reviewed yet.
    """
    want_lang = (language or "").strip().lower() or None
    per_artist = {}
    lang_seen = {}          # every language present, even when filtered out

    for test in tests:
        if test.test_type != "audio-segmentation":
            continue
        entries = test.json_entry if isinstance(test.json_entry, list) else []
        set_dir = _set_dir_of(entries)
        artist = _recorder_for(set_dir)
        language_name = _batch_language(entries)
        persona = (entries[0].get("persona") if entries else None) or "Unknown"
        lang_seen[language_name.lower()] = language_name
        if want_lang and language_name.lower() != want_lang:
            continue

        clips = len(entries)
        b_acc = b_rej = 0
        b_reasons = {}
        reviewed_ids = set()

        for r in ratings_by_test.get(test.id, []):
            if not (r.page_no_progress and r.completion_status in ("completed", "skipped")):
                continue
            rj = r.results_json if isinstance(r.results_json, dict) else {}
            ev = str(rj.get("evaluation") or "").strip().lower()
            if ev == "accept":
                b_acc += 1
                reviewed_ids.add(str(r.page_no_progress))
            elif ev == "reject":
                b_rej += 1
                reviewed_ids.add(str(r.page_no_progress))
                for slug in _reasons_of(rj):
                    b_reasons[slug] = b_reasons.get(slug, 0) + 1

        b_total = b_acc + b_rej
        # A clip counts as pending until somebody has reviewed it; two annotators
        # reviewing the same clip must not make it look like two clips are done.
        b_pending = max(0, clips - len(reviewed_ids))
        if not clips and not b_total:
            continue

        a = per_artist.setdefault(artist, {"artist": artist, "batches": [], "langs": {}})
        bucket = a["langs"].setdefault(language_name, _empty_bucket())
        bucket["clips"] += clips
        bucket["total"] += b_total
        bucket["accepted"] += b_acc
        bucket["rejected"] += b_rej
        bucket["pending"] += b_pending
        bucket["batch_count"] += 1
        for slug, cnt in b_reasons.items():
            bucket["_reasons"][slug] = bucket["_reasons"].get(slug, 0) + cnt

        a["batches"].append({
            "test_id": test.id,
            "description": test.description or "",
            "language": language_name,
            "persona": persona,
            "set_dir": set_dir,
            "clips": clips,
            "total": b_total,
            "accepted": b_acc,
            "rejected": b_rej,
            "pending": b_pending,
            "rejection_rate": round(100.0 * b_rej / b_total, 1) if b_total else 0.0,
        })

    artists = []
    overall = _empty_bucket()
    per_language = {}
    for a in per_artist.values():
        artist_bucket = _empty_bucket()
        by_language = {}
        for lang, bucket in a["langs"].items():
            _merge_bucket(artist_bucket, bucket)
            _merge_bucket(overall, bucket)
            _merge_bucket(per_language.setdefault(lang, _empty_bucket()), bucket)
            by_language[lang] = _finish_bucket(bucket)
        if not artist_bucket["clips"] and not artist_bucket["total"]:
            continue

        a["batches"].sort(key=lambda b: -b["rejection_rate"])
        artists.append(dict(
            _finish_bucket(artist_bucket),
            artist=a["artist"],
            batches=a["batches"],
            by_language=by_language,
        ))
    artists.sort(key=lambda x: -x["rejection_rate"])

    languages = sorted(
        (dict(_finish_bucket(b), language=lang) for lang, b in per_language.items()),
        key=lambda x: x["language"],
    )
    return {
        "artists": artists,
        "overall": _finish_bucket(overall),
        "languages": languages,
        # Every language on record, so a UI filter can offer them all.
        "all_languages": sorted(lang_seen.values()),
        "language_filter": language or None,
    }


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


_ARTIST_HEADERS = ["Artist", "Batches", "Total Clips", "Total Reviewed", "Accepted",
                   "Rejected", "Pending", "Rejection Rate %", "Pending %"]


def _artist_csv_cells(name, b):
    return [name, b["batch_count"], b["clips"], b["total"], b["accepted"],
            b["rejected"], b["pending"], b["rejection_rate"], b["pending_rate"]]


def artist_report_csv(stats):
    """Vendor-shareable CSV: per-artist rates (incl. pending), a per-language
    rollup, then the per-artist reason breakdown."""
    buf = io.StringIO()
    w = csv.writer(buf)
    if stats.get("language_filter"):
        w.writerow([f"Language filter: {stats['language_filter']}"])
        w.writerow([])
    w.writerow(_ARTIST_HEADERS)
    for a in stats["artists"]:
        w.writerow(_artist_csv_cells(a["artist"], a))
    o = stats["overall"]
    w.writerow(_artist_csv_cells("OVERALL", o))
    w.writerow([])

    # Per-artist × language, so the vendor can see which language is lagging.
    w.writerow(["Artist", "Language", "Batches", "Total Clips", "Total Reviewed",
                "Accepted", "Rejected", "Pending", "Rejection Rate %", "Pending %"])
    for a in stats["artists"]:
        for lang in sorted(a.get("by_language", {})):
            b = a["by_language"][lang]
            w.writerow([a["artist"], lang, b["batch_count"], b["clips"], b["total"],
                        b["accepted"], b["rejected"], b["pending"],
                        b["rejection_rate"], b["pending_rate"]])
    w.writerow([])

    w.writerow(["Language", "Batches", "Total Clips", "Total Reviewed", "Accepted",
                "Rejected", "Pending", "Rejection Rate %", "Pending %"])
    for l in stats.get("languages", []):
        w.writerow(_artist_csv_cells(l["language"], l))
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


def audio_clips_rows(tests, ratings_by_test, only_rejected=True, language=None,
                     include_pending=True):
    """One row per audio clip: who recorded it, the verdict, why, and a link that
    opens the clip in Saffron so the vendor can listen to it.

    include_pending adds the clips nobody has reviewed yet (evaluation 'pending'),
    so the export shows the whole batch instead of only the finished part. It is
    ignored when only_rejected is set.
    """
    want_lang = (language or "").strip().lower() or None
    rows = []
    for test in tests:
        if test.test_type != "audio-segmentation":
            continue
        entries = test.json_entry if isinstance(test.json_entry, list) else []
        by_id = {str(it.get("id")): it for it in entries}
        set_dir = _set_dir_of(entries)
        artist = _recorder_for(set_dir)
        language_name = _batch_language(entries)
        if want_lang and language_name.lower() != want_lang:
            continue
        persona = (entries[0].get("persona") if entries else None) or ""
        # excel set label, e.g. 'Set2' -- from the description tail
        set_label = ""
        parts = [p.strip() for p in (test.description or "").split(" - ")]
        if len(parts) >= 4:
            set_label = parts[3]

        reviewed_ids = set()
        for r in ratings_by_test.get(test.id, []):
            if not (r.page_no_progress and r.completion_status in ("completed", "skipped")):
                continue
            rj = r.results_json if isinstance(r.results_json, dict) else {}
            ev = str(rj.get("evaluation") or "").strip().lower()
            task_id = str(rj.get("id") or r.page_no_progress or "")
            if ev in ("accept", "reject"):
                reviewed_ids.add(task_id)
            if only_rejected and ev != "reject":
                continue
            item = by_id.get(task_id, {})
            reasons = [reason_label(x) for x in _reasons_of(rj)]
            rows.append({
                "artist": artist,
                "language": language_name,
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

        if only_rejected or not include_pending:
            continue
        for idx, item in enumerate(entries):
            task_id = str(item.get("id") if isinstance(item, dict) and "id" in item else (idx + 1))
            if task_id in reviewed_ids:
                continue
            rows.append({
                "artist": artist,
                "language": language_name,
                "persona": persona,
                "set": set_label,
                "test_id": test.id,
                "task_id": task_id,
                "speaker": item.get("speaker", "") if isinstance(item, dict) else "",
                "evaluation": "pending",
                "rejection_reasons": "",
                "custom_reason": "",
                "annotator": "",
                "transcript": ((item.get("transcript") if isinstance(item, dict) else "") or "")[:400],
                "link": task_link(test.id, task_id),
            })
    rows.sort(key=lambda x: (x["artist"], x["set"], x["task_id"]))
    return rows


def audio_clips_csv(tests, ratings_by_test, only_rejected=True, language=None,
                    include_pending=True):
    rows = audio_clips_rows(tests, ratings_by_test, only_rejected, language=language,
                            include_pending=include_pending)
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



