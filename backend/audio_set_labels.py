#!/usr/bin/env python3
"""
audio_set_labels.py — how an audio-segmentation batch is LABELLED in the UI.

The set number shown to users is the RECORDING EXCEL's set (English_Storyteller_Set2.xlsx
-> Set2), NOT the local setN directory (dir set5 can hold the Set2 excel).

Because the same excel set can legitimately be recorded/loaded in more than one batch
(e.g. dir set5 = Conv 1-19 and dir set6 = Conv 20-30 are both Set2), any set that appears
more than once is disambiguated in brackets with the recorder and the conversation range:

    Audio Segmentation - English - Storyteller - Set1
    Audio Segmentation - English - Storyteller - Set2 (Soniya, Conv 1-19)
    Audio Segmentation - English - Storyteller - Set2 (Soniya, Conv 20-30)

Sets that appear only once stay clean (no brackets). `relabel_all()` is idempotent and
recomputes every audio-segmentation description from scratch, so the loader can just call
it after every load and the labels stay consistent.
"""
import os
import re

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")


def set_dir_of(entries):
    """Local setN dir a batch's audio lives in, from the first task's audio_filename."""
    if not entries:
        return ""
    return str(entries[0].get("audio_filename", "")).split("/")[0]


def excel_set_label(set_dir):
    """'Set2' from the recording excel in the dir; None if there is no Set<n> excel."""
    d = os.path.join(AUDIO_DIR, set_dir)
    if not set_dir or not os.path.isdir(d):
        return None
    xl = [f for f in os.listdir(d) if f.endswith(".xlsx") and not f.startswith("~$")]
    if not xl:
        return None
    m = re.search(r"_Set(\d+)$", os.path.splitext(xl[0])[0], re.IGNORECASE)
    return f"Set{int(m.group(1))}" if m else None


def recorder_of(set_dir):
    """Voice actor for the batch, from <set_dir>/recorder.txt (written at download time)."""
    p = os.path.join(AUDIO_DIR, set_dir, "recorder.txt")
    try:
        with open(p, encoding="utf-8") as fh:
            return fh.read().strip() or None
    except Exception:
        return None


def conv_range(entries):
    """(lowest, highest) conversation number across a batch's task ids."""
    nums = []
    for it in entries or []:
        m = re.search(r"Conv_(\d+)_T_\d+", str(it.get("id", "")), re.IGNORECASE)
        if m:
            nums.append(int(m.group(1)))
    return (min(nums), max(nums)) if nums else (None, None)


def bracket_for(set_dir, entries):
    """'(Soniya, Conv 20-30)' / '(Conv 20-30)' / '(Soniya)' / '' — the disambiguator."""
    bits = []
    rec = recorder_of(set_dir)
    if rec:
        bits.append(rec)
    lo, hi = conv_range(entries)
    if lo is not None:
        bits.append(f"Conv {lo}-{hi}" if lo != hi else f"Conv {lo}")
    return f" ({', '.join(bits)})" if bits else ""


def relabel_all(db, Test, verbose=True):
    """Recompute every audio-segmentation description. Returns list of (id, old, new)."""
    tests = Test.query.filter_by(test_type="audio-segmentation").order_by(Test.id).all()

    info = []   # (test, base_desc, set_dir, entries)
    for t in tests:
        entries = t.json_entry if isinstance(t.json_entry, list) else []
        set_dir = set_dir_of(entries)
        label = excel_set_label(set_dir)
        if not label:
            continue  # no excel/Set<n> -> leave this row alone
        language = (entries[0].get("language") if entries else None) or "English"
        persona = (entries[0].get("persona") if entries else None) or "Unknown"
        base = f"Audio Segmentation - {language} - {persona} - {label}"
        info.append((t, base, set_dir, entries))

    # A base label used by more than one batch needs the bracket disambiguator.
    counts = {}
    for _t, base, _d, _e in info:
        counts[base] = counts.get(base, 0) + 1

    changes = []
    for t, base, set_dir, entries in info:
        new = base + (bracket_for(set_dir, entries) if counts[base] > 1 else "")
        if new != (t.description or ""):
            changes.append((t.id, t.description, new))
            t.description = new
    if changes:
        db.session.commit()
    if verbose:
        for tid, old, new in changes:
            print(f"  {tid}: {old!r}\n     -> {new!r}")
        if not changes:
            print("  (all audio-segmentation labels already correct)")
    return changes
