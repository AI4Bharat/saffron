#!/usr/bin/env python3
"""qc_inspect_worker.py <job_id> — inspect a Drive recordings link before loading it."""

import os
import re
import sys

# Both the sibling tools modules (qc_upload_jobs) and the backend root (main, application.*) must be importable.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import qc_upload_jobs as jobs

# This file lives in backend/tools/ -- the backend root is one directory up.
BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIO_SEG_BASE_DIR = os.path.join(BACKEND_DIR, "audio_segmentation")
DEFAULT_EXCEL_DRIVE_FOLDER = "https://drive.google.com/drive/folders/1nP_Eu7rtI_R49vd_s4c6JxzyaI-vb8HD"

# first two letters of the Title-cased language, matching docx_to_excel.py
LANG_BY_PREFIX = {
    "en": "english", "hi": "hindi", "te": "telugu", "ta": "tamil",
    "ka": "kannada", "od": "odia", "gu": "gujarati", "be": "bengali",
    "pu": "punjabi", "ur": "urdu",
    # Marathi and Malayalam collide on "Ma" — resolved by the admin in the dialog.
}


def conv_core(text):
    m = re.search(r"Conv_\d+_T_\d+", str(text), re.IGNORECASE)
    return m.group(0) if m else None


def next_set_name():
    nums = []
    if os.path.isdir(AUDIO_SEG_BASE_DIR):
        for d in os.listdir(AUDIO_SEG_BASE_DIR):
            m = re.fullmatch(r"set(\d+)", d.lower())
            if m and os.path.isdir(os.path.join(AUDIO_SEG_BASE_DIR, d)):
                nums.append(int(m.group(1)))
    return f"set{max(nums) + 1 if nums else 0}"


def list_folder(url):
    import gdown
    files = gdown.download_folder(url=url, skip_download=True, quiet=True, use_cookies=False)
    if not files:
        raise RuntimeError(
            "Could not list that Drive folder. Check the link is shared as "
            "'Anyone with the link' and points at a folder.")
    return files


def inspect_audio(audio_link, id_subfolder):
    """WAV inventory for the link, preferring an 'EXPORTED ID'-style subfolder."""
    files = list_folder(audio_link)
    wavs = [f for f in files
            if f.path.lower().endswith(".wav") and id_subfolder.lower() in f.path.lower()]
    used_subfolder = bool(wavs)
    if not wavs:
        # The admin usually pastes the ID folder itself, which is flat.
        wavs = [f for f in files if f.path.lower().endswith(".wav")]
    if not wavs:
        raise RuntimeError(
            f"No .wav files found in that folder (looked inside '{id_subfolder}' "
            f"and at the top level). Listed {len(files)} entr(ies).")

    stems = [os.path.splitext(os.path.basename(f.path))[0].replace("Copy of ", "").strip()
             for f in wavs]
    cores = [conv_core(s) for s in stems]
    good = [c for c in cores if c]

    convs, turns = set(), set()
    for c in good:
        m = re.match(r"Conv_(\d+)_T_(\d+)", c, re.IGNORECASE)
        if m:
            convs.add(int(m.group(1)))
            turns.add(int(m.group(2)))

    # Language from the stem prefix, e.g. "En_Conv_3_T_1" -> en -> english.
    lang, lang_evidence = None, ""
    prefixes = {}
    for s in stems:
        m = re.match(r"([A-Za-z]{2})_Conv_", s)
        if m:
            p = m.group(1).lower()
            prefixes[p] = prefixes.get(p, 0) + 1
    if prefixes:
        top = max(prefixes, key=prefixes.get)
        lang = LANG_BY_PREFIX.get(top)
        lang_evidence = (f"{prefixes[top]} of {len(stems)} WAVs are named '{top.title()}_Conv_...'"
                         + ("" if lang else f" — prefix '{top}' is ambiguous, please pick the language"))

    return wavs, {
        "wav_count": len(wavs),
        "named_ok": len(good),
        "unnamed": len(stems) - len(good),
        "conv_min": min(convs) if convs else None,
        "conv_max": max(convs) if convs else None,
        "conv_count": len(convs),
        "turns": sorted(turns),
        "used_id_subfolder": used_subfolder,
        "sample_names": sorted(stems)[:6],
        "language": lang,
        "language_evidence": lang_evidence,
    }


def index_excels(excel_link):
    """Every recording Excel on Drive as {language, persona, set, recorder, filename}."""
    files = list_folder(excel_link)
    out = []
    for f in files:
        base = os.path.basename(f.path).replace("Copy of ", "").strip()
        if not base.lower().endswith(".xlsx") or base.startswith("~$"):
            continue
        stem = os.path.splitext(base)[0]
        m = re.match(r"([A-Za-z]+)_(.+)_Set(\d+)$", stem, re.IGNORECASE)
        if not m:
            continue
        parts = f.path.split("/")
        recorder = ""
        if len(parts) >= 2 and " - " in parts[-2]:
            recorder = parts[-2].split(" - ")[-1].strip()
        out.append({
            "language": m.group(1).lower(),
            # loader wants the persona lowercased with underscores, as in the filename
            "persona": m.group(2).lower(),
            "persona_label": m.group(2).replace("_", " ").title(),
            "set": int(m.group(3)),
            "recorder": recorder,
            "filename": base,
            "drive_path": f.path,
        })
    out.sort(key=lambda x: (x["language"], x["persona"], x["set"]))
    return out


def drive_wav_sizes(wavs, workers=8):
    """{stem: byte size} for the folder's WAVs, via a HEAD per file."""
    import concurrent.futures
    import subprocess

    def head(f):
        stem = os.path.splitext(os.path.basename(f.path))[0].replace("Copy of ", "").strip()
        url = f"https://drive.google.com/uc?export=download&id={f.id}"
        try:
            out = subprocess.run(["curl", "-sIL", "--max-time", "25", url],
                                 capture_output=True, text=True).stdout
            sizes = [int(m.group(1)) for m in
                     re.finditer(r"(?im)^content-length:\s*(\d+)", out)]
            # The first hop is a 303 with content-length 0; the real file is the last.
            real = [s for s in sizes if s > 0]
            return stem, (real[-1] if real else None)
        except Exception:
            return stem, None

    out = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for stem, size in pool.map(head, wavs):
            out[stem] = size
    return out


def saffron_audio_batches():
    """Loaded audio-seg batches with the on-disk sizes of their clips, so the dialog can say whether this exact audio is already in Saffron."""
    from main import app  # noqa: F401
    from application.models import Test

    out = []
    for t in Test.query.filter(Test.test_type == "audio-segmentation").order_by(Test.id).all():
        entries = t.json_entry if isinstance(t.json_entry, list) else []
        first = (entries[0] if entries else {}) or {}
        set_dir = first.get("set_dir") or ""
        d = os.path.join(AUDIO_SEG_BASE_DIR, set_dir)
        clips = {}
        if set_dir and os.path.isdir(d):
            for n in os.listdir(d):
                if n.endswith(".wav"):
                    try:
                        clips[os.path.splitext(n)[0]] = os.path.getsize(os.path.join(d, n))
                    except OSError:
                        pass
        out.append({"test_id": t.id, "description": t.description or "",
                    "set_dir": set_dir, "num_tasks": len(entries), "clips": clips})
    return out


def compare_audio(drive_sizes, batches):
    """Drive folder vs every loaded batch, by clip name AND by exact byte size."""
    drive_named = set(drive_sizes)
    rows = []
    for b in batches:
        common = drive_named & set(b["clips"])
        identical = sum(1 for s in common
                        if drive_sizes.get(s) is not None and drive_sizes[s] == b["clips"][s])
        if not common:
            continue
        if identical and identical == len(drive_named) and identical == len(b["clips"]):
            verdict = "same audio"
        elif identical:
            verdict = "partly the same"
        else:
            verdict = "different recording"
        rows.append({
            "test_id": b["test_id"], "description": b["description"],
            "set_dir": b["set_dir"], "batch_clips": len(b["clips"]),
            "names_common": len(common), "bytes_identical": identical,
            "verdict": verdict,
        })
    rows.sort(key=lambda r: (-r["bytes_identical"], -r["names_common"]))
    return rows


def _norm(s):
    """Squash a label to comparable form: 'Story Teller' and 'storyteller' both become 'storyteller', so the Drive folder's spacing cannot cause a mismatch."""
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def loaded_sets():
    """The audio-segmentation batches already in Saffron."""
    from main import app  # noqa: F401  (pushes the app context on import)
    from application.models import Test

    out = []
    for t in Test.query.filter(Test.test_type == "audio-segmentation").order_by(Test.id).all():
        entries = t.json_entry if isinstance(t.json_entry, list) else []
        first = (entries[0] if entries else {}) or {}
        m = re.search(r"(\d+)", str(first.get("excel_set") or ""))
        if not m:
            m = re.search(r"Set\s*(\d+)", t.description or "", re.IGNORECASE)
        out.append({
            "test_id": t.id,
            "description": t.description or "",
            "language": (first.get("language") or "").lower(),
            "persona": (first.get("persona") or "").lower(),
            "set": int(m.group(1)) if m else None,
            "set_dir": first.get("set_dir") or "",
            "num_tasks": len(entries),
        })
    return out


def is_already_loaded(candidate, loaded):
    """Has this exact (language, persona, set) been loaded into Saffron?"""
    lang_n = _norm(candidate["language"])
    pers_n = _norm(candidate["persona"])
    for b in loaded:
        if b["set"] != candidate["set"]:
            continue
        b_lang, b_pers = _norm(b["language"]), _norm(b["persona"])
        # Fall back to the description when a batch predates the structured fields.
        hay = _norm(b["description"])
        lang_ok = (b_lang == lang_n) if b_lang else (lang_n in hay)
        pers_ok = (b_pers == pers_n) if b_pers else (pers_n in hay)
        if lang_ok and pers_ok:
            return True
    return False


def main():
    job_id = sys.argv[1]
    job = jobs.read_job(job_id)
    if not job:
        print(f"no such job: {job_id}")
        return 1
    p = job.get("params") or {}
    jobs.worker_start(job_id)

    try:
        audio_link = (p.get("audio_link") or "").strip()
        if not audio_link:
            raise RuntimeError("No Drive link given.")
        id_subfolder = p.get("id_subfolder") or "EXPORTED ID"
        excel_link = p.get("excel_link") or DEFAULT_EXCEL_DRIVE_FOLDER

        jobs.worker_progress(job_id, "Listing the recordings folder on Drive…")
        wavs, audio = inspect_audio(audio_link, id_subfolder)
        print(f"[+] {audio['wav_count']} WAV(s); language guess = {audio['language']}")

        jobs.worker_progress(job_id, "Reading the shared recording-Excel folder…")
        excels = index_excels(excel_link)
        print(f"[+] {len(excels)} recording Excel(s) on Drive")

        jobs.worker_progress(job_id, "Checking which sets are already loaded…")
        already = loaded_sets()

        lang = audio.get("language")
        candidates = []
        for e in excels:
            if lang and e["language"] != lang:
                continue
            candidates.append({**e, "already_loaded": is_already_loaded(e, already)})

        # The real cross-check: THIS audio against the audio already in Saffron, compared by exact byte size (see drive_wav_sizes for why names alone lie).
        jobs.worker_progress(job_id, f"Measuring {len(wavs)} clip(s) on Drive…")
        drive_sizes = drive_wav_sizes(wavs)
        measured = sum(1 for v in drive_sizes.values() if v)
        print(f"[+] sized {measured}/{len(drive_sizes)} clip(s)")

        jobs.worker_progress(job_id, "Comparing against the audio already in Saffron…")
        audio_compare = compare_audio(drive_sizes, saffron_audio_batches())
        audio["total_bytes"] = sum(v for v in drive_sizes.values() if v)
        audio["sized_ok"] = measured
        top = audio_compare[0] if audio_compare else None
        print(f"[+] closest batch: {top['test_id'] if top else 'none'} "
              f"({top['verdict'] if top else 'no overlap'})")

        # Unloaded first: that is almost always what the admin is uploading.
        candidates.sort(key=lambda c: (c["already_loaded"], c["persona"], c["set"]))
        suggestion = next((c for c in candidates if not c["already_loaded"]), None)

        jobs.worker_done(job_id, {
            "audio": audio,
            "candidates": candidates,
            "audio_compare": audio_compare,
            "excel_total": len(excels),
            "suggestion": suggestion,
            "next_set_dir": next_set_name(),
            "loaded_count": len(already),
            "note": ("Persona and set cannot be read from the link — the shared folder is "
                     "usually named 'ID', Drive exposes no parent folder, and every set "
                     "reuses the same Conv_N_T_M ids. Confirm them below."),
        })
        print("[+] inspect complete")
        return 0
    except Exception as e:
        import traceback
        traceback.print_exc()
        jobs.worker_failed(job_id, e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
