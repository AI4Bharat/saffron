import os
import re
import json
import time
import glob
import argparse
from copy import deepcopy
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import google.generativeai as genai
from tqdm import tqdm

# ============================================================================
# Transliteration (NOT translation) of code-mixed Indian-language conversations.
#
# Goal: take each native-script string (Devanagari, Kannada, Telugu, Tamil,
# Odia, ...) and rewrite it in the Latin/English alphabet so it reads the way an
# Indian would naturally TYPE the same sentence in roman letters — pronunciation
# preserved, language unchanged. English words, technical jargon, units and all
# LaTeX equations are copied through verbatim. A new key is added beside each
# original field rather than overwriting it.
# ============================================================================

MODEL_NAME = "gemini-3.5-flash"

API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAeDsSzICRb3eS25IWGZOi-N7NyfoBAK2M")
if not API_KEY:
    print("Error: GEMINI_API_KEY environment variable is not set.")
    exit(1)

genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = """You are an expert TRANSLITERATOR (romanizer) of Indian languages. You convert text
written in a native Indian script (Devanagari, Bengali, Kannada, Telugu, Tamil, Malayalam, Odia, Gujarati,
Urdu, etc.) into the Latin (English) alphabet. This is TRANSLITERATION, NOT TRANSLATION: you change only the
SCRIPT, never the language. The words stay exactly what they are — you simply spell them out in roman letters
so a reader gets the same PRONUNCIATION.

=== HOW TO ROMANIZE ===
Write each native-script word the natural, intuitive way Indians actually type their own language in roman
letters on a phone — e.g. Devanagari "क्या हुआ?" -> "kya hua?", "मैं समझ गया" -> "main samajh gaya",
Kannada "ಏನಾಯ್ತು" -> "enaaytu". Use ONLY plain ASCII Latin letters and ordinary punctuation. Do NOT use
academic diacritics (no ā, ṣ, ṇ, ś, ḥ, etc.) — keep it the everyday, readable WhatsApp/chat style.

=== WHAT TO LEAVE UNTOUCHED (copy verbatim) ===
1. Any word or token ALREADY in the Latin/English alphabet — technical and scientific terms, jargon, units,
   variable names, proper nouns already in English, and common code-switched words (actually, basically,
   setup, point, value, okay, etc.). Reproduce them EXACTLY, unchanged. Do not "re-spell" or translate them.
2. MATH PLACEHOLDERS that look like @@0@@, @@1@@, @@2@@ ... Each stands in for a hidden equation. Copy every
   placeholder EXACTLY where it appears — never translate, modify, renumber, split, space out, merge or drop
   it, and never invent new ones.
3. All numbers, punctuation, symbols, capitalization of English words, and spacing/structure.

=== HARD RULES ===
- Do NOT translate. The output must be the SAME sentence, same words, same meaning — only the native-script
  portions are now spelled in roman letters. Never substitute an English synonym for a native word.
- Do NOT add, drop, reorder, explain or gloss anything. No parentheses, no notes.
- Keep every JSON key and the structure EXACTLY unchanged. Transform only the string VALUES.
- Return ONLY the JSON object, nothing else.
"""

model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_INSTRUCTION)

# --- LaTeX masking -----------------------------------------------------------
# This dataset delimits math in several ways. Order matters: match the longer
# delimiters ($$...$$, \[...\], \(...\)) before the single-$ inline form so a
# display-math block is never split. Masking ALL of these behind @@N@@ tokens
# keeps every equation out of the model's reach, so it comes back byte-for-byte.
_MATH_RE = re.compile(
    r'\$\$.*?\$\$'      # $$ ... $$  (display math)
    r'|\\\[.*?\\\]'     # \[ ... \]
    r'|\\\(.*?\\\)'     # \( ... \)
    r'|\$.*?\$',        # $ ... $    (inline math — by far the most common here)
    re.DOTALL,
)
_PLACEHOLDER_RE = re.compile(r'@@\d+@@')
_INVALID_ESCAPE_RE = re.compile(r'\\(?![\\"/bfnrtu])')

# Fields (besides dialogue turns) that get a parallel *_transliterated key.
SCENE_FIELDS = ["misconception_text", "pre_scene", "post_scene"]


def mask_math(text, store):
    """Replace every LaTeX span with a backslash-free @@N@@ placeholder so the model
    never sees a backslash and the equations come back byte-for-byte identical."""
    if not isinstance(text, str) or not text:
        return text

    def repl(match):
        token = f"@@{len(store)}@@"
        store.append(match.group(0))
        return token

    return _MATH_RE.sub(repl, text)


def unmask_math(text, store):
    """Restore the original LaTeX spans hidden behind @@N@@ placeholders."""
    if not isinstance(text, str):
        return text
    for i, span in enumerate(store):
        text = text.replace(f"@@{i}@@", span)
    return text


def _repair_latex_escapes(s):
    return _INVALID_ESCAPE_RE.sub(r'\\\\', s)


def _try_load(candidate):
    candidate = candidate.lstrip()
    for variant in (candidate, _repair_latex_escapes(candidate)):
        try:
            return json.loads(variant)
        except json.JSONDecodeError:
            try:
                return json.JSONDecoder().raw_decode(variant)[0]
            except json.JSONDecodeError:
                continue
    return json.loads(candidate)


def extract_json(text):
    """Robustly extract and parse JSON from the model response."""
    text_stripped = text.strip()
    try:
        return _try_load(text_stripped)
    except json.JSONDecodeError:
        pass
    if "```" in text_stripped:
        if "```json" in text_stripped:
            try:
                content = text_stripped.split("```json")[1].split("```")[0].strip()
                return _try_load(content)
            except (IndexError, json.JSONDecodeError):
                pass
        try:
            content = text_stripped.split("```")[1].split("```")[0].strip()
            return _try_load(content)
        except (IndexError, json.JSONDecodeError):
            pass
    try:
        start = text_stripped.find("{")
        end = text_stripped.rfind("}")
        if start != -1 and end != -1:
            return _try_load(text_stripped[start:end + 1])
    except json.JSONDecodeError:
        pass
    raise ValueError(f"Could not parse valid JSON from response: {text}")


def _collect_texts(payload):
    texts = []
    for key, val in payload.items():
        if key == "dialogue" and isinstance(val, list):
            for turn in val:
                if isinstance(turn, dict):
                    texts.append(turn.get("text", "") or "")
        elif isinstance(val, str):
            texts.append(val)
    return texts


def _placeholders_of(payload):
    found = []
    for t in _collect_texts(payload):
        found.extend(_PLACEHOLDER_RE.findall(t))
    return sorted(found)


def validate_latex_preserved(source_payload, out_payload):
    """The exact multiset of @@N@@ tokens in the source must survive in the output."""
    return _placeholders_of(source_payload) == _placeholders_of(out_payload)


def transliterate_record(record):
    """Build a masked payload of the translatable strings, ask Gemini to romanize them,
    then merge the romanized text back as NEW keys beside the originals."""
    payload = {}
    for f in SCENE_FIELDS:
        if record.get(f):
            payload[f] = record.get(f, "")
    if "dialogue" in record:
        payload["dialogue"] = [
            {"turn_index": turn.get("turn_index"), "text": turn.get("text", "")}
            for turn in record["dialogue"]
        ]

    # Hide LaTeX behind @@N@@ placeholders.
    math_store = []
    for key, val in list(payload.items()):
        if key == "dialogue":
            for turn in val:
                turn["text"] = mask_math(turn.get("text", ""), math_store)
        else:
            payload[key] = mask_math(val, math_store)

    base_prompt = (
        "Transliterate (romanize) every string value in this JSON record from its native Indian script "
        "into the Latin/English alphabet, following the rules: change only the script, never the language; "
        "keep words that are already in English, plus all units, jargon and @@N@@ tokens, exactly as-is; "
        "use natural everyday roman spelling with plain ASCII letters (no diacritics). Keep all keys and "
        "structure identical and return only the JSON.\n\n"
        f"{json.dumps(payload, ensure_ascii=False)}"
    )

    out_payload = None
    for attempt in range(3):
        prompt = base_prompt
        if attempt > 0:
            prompt += ("\n\n=== RETRY ===\nYour previous output altered or dropped some @@N@@ equation "
                       "placeholders. Reproduce EVERY @@N@@ token from the source exactly once, unchanged "
                       "and in place, and romanize only the native-script text.")
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2,
                "top_p": 0.9,
            },
        )
        candidate = extract_json(response.text)
        out_payload = candidate
        if validate_latex_preserved(payload, candidate):
            break

    # Restore the original LaTeX equations.
    for key, val in out_payload.items():
        if key == "dialogue" and isinstance(val, list):
            for turn in val:
                if isinstance(turn, dict):
                    turn["text"] = unmask_math(turn.get("text", ""), math_store)
        else:
            out_payload[key] = unmask_math(val, math_store)

    # Merge romanized text back as NEW keys beside the originals.
    merged = deepcopy(record)
    for f in SCENE_FIELDS:
        if f in out_payload:
            merged[f"{f}_transliterated"] = out_payload.get(f, "")
    if "dialogue" in out_payload and "dialogue" in merged:
        trans_turns = {t.get("turn_index"): t.get("text", "") for t in out_payload["dialogue"]}
        for turn in merged["dialogue"]:
            idx = turn.get("turn_index")
            if idx in trans_turns:
                turn["transliterated"] = trans_turns[idx]
    return merged


def transliterate_with_retry(record, index):
    for attempt in range(3):
        try:
            return index, transliterate_record(record)
        except Exception as e:
            if attempt == 2:
                print(f"\nFailed to transliterate record {record.get('id')} (idx {index}) after 3 attempts: {e}")
                raise
            time.sleep(2)


def _is_done(rec):
    """A cached record counts as already transliterated if its scene keys are present
    and every dialogue turn carries a 'transliterated' key."""
    if not any(f"{f}_transliterated" in rec for f in SCENE_FIELDS):
        # records may legitimately lack scene text; fall through to dialogue check
        pass
    dialogue = rec.get("dialogue") or []
    if dialogue:
        return all("transliterated" in t for t in dialogue)
    return any(f"{f}_transliterated" in rec for f in SCENE_FIELDS)


def _save_progress(out_file, records_indexed):
    sorted_records = [r for _, r in sorted(records_indexed, key=lambda x: x[0])]
    temp_file = out_file + ".tmp"
    try:
        with open(temp_file, "w", encoding="utf-8") as out_f:
            for r in sorted_records:
                out_f.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(temp_file, out_file)
    except Exception as e:
        print(f"\nWarning: failed to auto-save progress to {out_file}: {e}")


def process_file(in_file, max_workers, max_records=None):
    stem, ext = os.path.splitext(in_file)
    suffix = "_transliterated"
    # Keep small test runs (--max-records) from clobbering a full output file.
    if max_records:
        suffix += f"_sample{max_records}"
    out_file = f"{stem}{suffix}{ext}"

    records = []
    with open(in_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line.strip()))
    if max_records:
        records = records[:max_records]
    if not records:
        print(f"  [skip] {in_file}: empty.")
        return

    # Resume: reuse already-finished records from a previous run.
    cache = {}
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as cf:
                for line in cf:
                    if not line.strip():
                        continue
                    rec = json.loads(line.strip())
                    if "id" in rec and _is_done(rec):
                        cache[rec["id"]] = rec
        except Exception as e:
            print(f"  Warning: could not read cache {out_file}: {e}")

    done_indexed = []
    todo = []
    for i, rec in enumerate(records):
        rid = rec.get("id")
        if rid and rid in cache:
            done_indexed.append((i, cache[rid]))
        else:
            todo.append((i, rec))

    name = os.path.relpath(in_file)
    if not todo:
        _save_progress(out_file, done_indexed)
        print(f"  [done] {name}: all {len(records)} records already transliterated.")
        return

    workers = min(max_workers, len(todo))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(transliterate_with_retry, rec, i) for i, rec in todo]
        last_save = time.time()
        for future in tqdm(as_completed(futures), total=len(todo), desc=os.path.basename(in_file)):
            try:
                index, out = future.result()
                done_indexed.append((index, out))
                if time.time() - last_save > 10:
                    _save_progress(out_file, done_indexed)
                    last_save = time.time()
            except Exception:
                pass

    _save_progress(out_file, done_indexed)
    print(f"  [saved] {name}: {len(done_indexed)}/{len(records)} -> {os.path.basename(out_file)}")


HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(HERE, "conversation_editable_tasks")


def main():
    parser = argparse.ArgumentParser(
        description="Transliterate (romanize) native-script Indian-language conversation JSONL files into "
                    "the Latin alphabet, adding a 'transliterated' key beside each dialogue turn and scene "
                    "field. English text, jargon and LaTeX are preserved verbatim."
    )
    parser.add_argument("--root", default=DEFAULT_ROOT,
                        help="Directory containing the conversation JSONL files. "
                             "Default: ./conversation_editable_tasks")
    parser.add_argument("--no-recurse", action="store_true",
                        help="Only process .jsonl files directly in --root (skip subfolders).")
    parser.add_argument("--files", nargs="+", metavar="PATH",
                        help="Process only these specific .jsonl files (paths or glob patterns), "
                             "instead of scanning --root. Good for testing on a couple of files first.")
    parser.add_argument("--limit", type=int, metavar="N",
                        help="Process only the first N matched files (a quick subset test).")
    parser.add_argument("--max-records", type=int, metavar="N",
                        help="Per file, transliterate only the first N records, writing to a separate "
                             "*_transliterated_sampleN.jsonl file. Cheapest way to sanity-check output.")
    parser.add_argument("--dry-run", action="store_true",
                        help="List the files that WOULD be processed, then exit (no API calls).")
    parser.add_argument("--workers", type=int, default=15,
                        help="Max parallel Gemini calls per file. Default: 15")
    args = parser.parse_args()

    # Resolve the working set of input files.
    if args.files:
        files = []
        for pat in args.files:
            matched = sorted(glob.glob(pat))
            if matched:
                files.extend(matched)
            elif os.path.exists(pat):
                files.append(pat)
            else:
                print(f"  Warning: no match for {pat!r}")
        files = sorted(dict.fromkeys(files))  # de-dup, keep order
    elif args.no_recurse:
        files = sorted(glob.glob(os.path.join(args.root, "*.jsonl")))
    else:
        files = sorted(glob.glob(os.path.join(args.root, "**", "*.jsonl"), recursive=True))

    # Never reprocess our own outputs (full or sample).
    files = [f for f in files if "_transliterated" not in os.path.basename(f)]
    if args.limit:
        files = files[:args.limit]

    if not files:
        print("No matching .jsonl files found.")
        return

    if args.dry_run:
        print(f"[dry-run] would process {len(files)} file(s):")
        for f in files:
            print(f"  {f}")
        return

    scope = f"first {args.max_records} record(s) of " if args.max_records else ""
    print(f"Transliterating {scope}{len(files)} file(s) using {MODEL_NAME}...")
    t_start = time.time()
    for f in files:
        process_file(f, args.workers, args.max_records)
    print(f"\nAll files done in {time.time() - t_start:.1f}s.")


if __name__ == "__main__":
    main()
