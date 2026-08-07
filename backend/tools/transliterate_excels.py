#!/usr/bin/env python3
"""Romanize (transliterate) the native-script text inside conversation EXCEL files."""

import argparse
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed

import openpyxl
from tqdm import tqdm

import google.generativeai as genai

MODEL_NAME = os.environ.get('TRANSLIT_MODEL', 'gemini-3.5-flash')
API_KEY = os.environ.get('GEMINI_API_KEY')  # secrets live in .env, never in source
if not API_KEY:
    print('Error: set GEMINI_API_KEY.')
    sys.exit(1)
genai.configure(api_key=API_KEY)

SYSTEM_INSTRUCTION = """You are an expert TRANSLITERATOR (romanizer) of Indian languages. You convert text
written in a native Indian script (Devanagari, Bengali, Kannada, Telugu, Tamil, Malayalam, Odia, Gujarati,
Gurmukhi, Urdu, Assamese, etc.) into the Latin (English) alphabet. This is TRANSLITERATION, NOT TRANSLATION:
you change only the SCRIPT, never the language. The words stay exactly what they are - you simply spell them
out in roman letters so a reader gets the same PRONUNCIATION.

=== HOW TO ROMANIZE ===
Write each native-script word the natural, intuitive way Indians actually type their own language in roman
letters on a phone - e.g. Devanagari "क्या हुआ?" -> "kya hua?", "मैं समझ गया" -> "main samajh gaya",
Kannada "ಏನಾಯ್ತು" -> "enaaytu", Tamil "என்ன ஆச்சு" -> "enna aachu". Use ONLY plain ASCII Latin letters and
ordinary punctuation. Do NOT use academic diacritics (no a-macron, s-dot, n-dot etc.) - keep it the everyday,
readable WhatsApp/chat style.

=== WHAT TO LEAVE UNTOUCHED (copy verbatim) ===
1. Any word or token ALREADY in the Latin/English alphabet - technical and scientific terms, jargon, units,
   variable names, proper nouns already in English, and common code-switched words (actually, basically,
   setup, point, value, okay, etc.). Reproduce them EXACTLY, unchanged. Do not "re-spell" or translate them.
2. MATH PLACEHOLDERS that look like @@0@@, @@1@@, @@2@@ ... Each stands in for a hidden equation. Copy every
   placeholder EXACTLY where it appears - never translate, modify, renumber, split, space out, merge or drop
   it, and never invent new ones.
3. All numbers, punctuation, symbols, capitalization of English words, and spacing/structure.

=== HARD RULES ===
- Do NOT translate. The output must be the SAME sentence, same words, same meaning - only the native-script
  portions are now spelled in roman letters. Never substitute an English synonym for a native word.
- Do NOT add, drop, reorder, explain or gloss anything. No parentheses, no notes.
- You are given a JSON object {"items":[{"i":<int>,"t":"<text>"}, ...]}. Return a JSON object with the SAME
  shape, the SAME "i" values, in the SAME order, with only the "t" strings romanized. Return ONLY that JSON.
"""

model = genai.GenerativeModel(model_name=MODEL_NAME, system_instruction=SYSTEM_INSTRUCTION)

# --- LaTeX / math masking (same delimiters as transliterate_conversations.py) ---
_MATH_RE = re.compile(
    r'\$\$.*?\$\$'
    r'|\\\[.*?\\\]'
    r'|\\\(.*?\\\)'
    r'|\$.*?\$',
    re.DOTALL,
)
_PLACEHOLDER_RE = re.compile(r'@@\d+@@')

# Unicode blocks of every script this corpus can contain.
_INDIC_RANGES = [
    (0x0900, 0x097F),  # Devanagari (Hindi, Marathi, Sanskrit)
    (0x0980, 0x09FF),  # Bengali / Assamese
    (0x0A00, 0x0A7F),  # Gurmukhi (Punjabi)
    (0x0A80, 0x0AFF),  # Gujarati
    (0x0B00, 0x0B7F),  # Odia
    (0x0B80, 0x0BFF),  # Tamil
    (0x0C00, 0x0C7F),  # Telugu
    (0x0C80, 0x0CFF),  # Kannada
    (0x0D00, 0x0D7F),  # Malayalam
    (0x0D80, 0x0DFF),  # Sinhala
    (0x0600, 0x06FF),  # Arabic (Urdu)
    (0x0750, 0x077F),  # Arabic supplement
    (0xFB50, 0xFDFF),  # Arabic presentation forms A
    (0xFE70, 0xFEFF),  # Arabic presentation forms B
    (0x1CD0, 0x1CFF),  # Vedic extensions
    (0xA8E0, 0xA8FF),  # Devanagari extended
]


def needs_transliteration(text):
    if not isinstance(text, str) or not text.strip():
        return False
    for ch in text:
        cp = ord(ch)
        for lo, hi in _INDIC_RANGES:
            if lo <= cp <= hi:
                return True
    return False


def mask_math(text, store):
    def repl(m):
        token = f"@@{len(store)}@@"
        store.append(m.group(0))
        return token
    return _MATH_RE.sub(repl, text)


def unmask_math(text, store):
    if not isinstance(text, str):
        return text
    for i, span in enumerate(store):
        text = text.replace(f"@@{i}@@", span)
    return text


def extract_json(text):
    """Parse the model's JSON reply, tolerating code fences and stray prose."""
    s = (text or '').strip()
    for candidate in (s,):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
    if '```' in s:
        part = s.split('```json')[-1] if '```json' in s else s.split('```')[1] if s.count('```') > 1 else s
        part = part.split('```')[0].strip()
        try:
            return json.loads(part)
        except json.JSONDecodeError:
            pass
    a, b = s.find('{'), s.rfind('}')
    if a != -1 and b != -1:
        return json.loads(s[a:b + 1])
    raise ValueError('no JSON in response')


def _looks_romanized(out, src):
    """Reject a reply that came back still in native script (the model ignored the instruction) or that dropped an equation placeholder."""
    if sorted(_PLACEHOLDER_RE.findall(src)) != sorted(_PLACEHOLDER_RE.findall(out)):
        return False
    if needs_transliteration(out):
        return False
    return bool(out.strip())


class Translator:
    """Batched, retrying, cache-backed cell translator."""

    def __init__(self, batch_size=12, tries=4, cache=None):
        self.batch_size = batch_size
        self.tries = tries
        self.cache = cache if cache is not None else {}
        self.lock = threading.Lock()
        self.calls = 0
        self.failures = 0

    @staticmethod
    def key(text):
        return hashlib.sha1(text.encode('utf-8')).hexdigest()

    def _call(self, payload_items):
        prompt = ('Romanize every "t" value below from its native Indian script into the Latin '
                  'alphabet. Change only the script, never the language. Keep @@N@@ tokens, English '
                  'words, numbers and punctuation exactly as they are. Return the same JSON shape '
                  'with the same "i" values.\n\n'
                  + json.dumps({'items': payload_items}, ensure_ascii=False))
        resp = model.generate_content(
            prompt,
            generation_config={'response_mime_type': 'application/json',
                               'temperature': 0.1, 'top_p': 0.9},
        )
        with self.lock:
            self.calls += 1
        data = extract_json(resp.text)
        items = data.get('items') if isinstance(data, dict) else data
        if not isinstance(items, list):
            raise ValueError('reply had no items list')
        return {int(it['i']): str(it.get('t', '')) for it in items if 'i' in it}

    def translate_many(self, texts):
        """texts: list[str] -> dict[str, (romanized, status)] keyed by the source text."""
        out = {}
        pending = []
        for t in texts:
            k = self.key(t)
            if k in self.cache:
                out[t] = (self.cache[k], 'cached')
            elif t not in out:
                pending.append(t)

        for start in range(0, len(pending), self.batch_size):
            chunk = pending[start:start + self.batch_size]
            stores = []
            payload = []
            for i, t in enumerate(chunk):
                store = []
                payload.append({'i': i, 't': mask_math(t, store)})
                stores.append(store)

            got = {}
            for attempt in range(1, self.tries + 1):
                try:
                    got = self._call(payload)
                    ok = all(i in got and _looks_romanized(got[i], payload[i]['t'])
                             for i in range(len(chunk)))
                    if ok:
                        break
                except Exception:
                    got = {}
                time.sleep(min(2 ** attempt, 30) * (0.6 + 0.8 * random.random()))

            for i, src in enumerate(chunk):
                romanized = got.get(i)
                status = 'ok'
                if romanized is None or not _looks_romanized(romanized, payload[i]['t']):
                    romanized, status = self._one(src)
                else:
                    romanized = unmask_math(romanized, stores[i])
                out[src] = (romanized, status)
                if status in ('ok', 'ok-single'):
                    with self.lock:
                        self.cache[self.key(src)] = romanized
                else:
                    with self.lock:
                        self.failures += 1
        return out

    def _one(self, text):
        """Last resort: one cell on its own. Returns (text, status)."""
        store = []
        masked = mask_math(text, store)
        for attempt in range(1, self.tries + 1):
            try:
                got = self._call([{'i': 0, 't': masked}])
                cand = got.get(0)
                if cand and _looks_romanized(cand, masked):
                    return unmask_math(cand, store), 'ok-single'
            except Exception:
                pass
            time.sleep(min(2 ** attempt, 30))
        return text, 'failed'      # keep the ORIGINAL; never write junk


# workbook handling

def load_cache(jsonl_path):
    cache = {}
    if not os.path.exists(jsonl_path):
        return cache
    try:
        with open(jsonl_path, encoding='utf-8') as fh:
            for line in fh:
                if not line.strip():
                    continue
                rec = json.loads(line)
                if rec.get('status') in ('ok', 'ok-single', 'cached') and rec.get('original'):
                    cache[Translator.key(rec['original'])] = rec.get('transliterated', '')
    except Exception:
        pass
    return cache


def process_workbook(src_path, in_root, out_root, translator_factory, force=False):
    rel = os.path.relpath(src_path, in_root)
    out_xlsx = os.path.join(out_root, rel)
    out_jsonl = os.path.splitext(out_xlsx)[0] + '.jsonl'
    os.makedirs(os.path.dirname(out_xlsx), exist_ok=True)

    if os.path.exists(out_xlsx) and not force:
        marker = out_xlsx + '.done'
        if os.path.exists(marker):
            return {'file': rel, 'skipped': True, 'cells': 0, 'failed': 0}

    wb = openpyxl.load_workbook(src_path)
    cache = load_cache(out_jsonl)
    translator = translator_factory(cache)

    records = []
    cells_done = 0
    failed = 0

    for sheet in wb.worksheets:
        if sheet.max_row is None or sheet.max_row < 1:
            continue
        header = [c.value for c in sheet[1]]

        # Which columns hold native-script text? Decide from the data, not the header name, so this works for every layout in the corpus.
        target_cols = []
        for col_idx in range(1, sheet.max_column + 1):
            hits = 0
            for row_idx in range(2, min(sheet.max_row, 60) + 1):
                if needs_transliteration(sheet.cell(row=row_idx, column=col_idx).value):
                    hits += 1
                    if hits >= 1:
                        break
            if hits:
                target_cols.append(col_idx)
        if not target_cols:
            continue

        # Collect the work for this sheet, then translate it in batches.
        work = {}          # col -> {row: text}
        texts = []
        for col_idx in target_cols:
            col_map = {}
            for row_idx in range(2, sheet.max_row + 1):
                val = sheet.cell(row=row_idx, column=col_idx).value
                if needs_transliteration(val):
                    col_map[row_idx] = str(val)
                    texts.append(str(val))
            work[col_idx] = col_map
        if not texts:
            continue

        results = translator.translate_many(list(dict.fromkeys(texts)))

        # Write each transliteration into a NEW column immediately to the right of the source column (inserted right-to-left so earlier indexes hold).
        for col_idx in sorted(target_cols, reverse=True):
            sheet.insert_cols(col_idx + 1)
            head = header[col_idx - 1] if col_idx - 1 < len(header) else f'Column{col_idx}'
            head = str(head) if head is not None else f'Column{col_idx}'
            sheet.cell(row=1, column=col_idx + 1).value = f'{head}_transliterated'
            for row_idx, src in work[col_idx].items():
                romanized, status = results.get(src, (src, 'failed'))
                sheet.cell(row=row_idx, column=col_idx + 1).value = romanized
                cells_done += 1
                if status == 'failed':
                    failed += 1
                records.append({
                    'file': rel,
                    'sheet': sheet.title,
                    'row': row_idx,
                    'column': head,
                    'id': sheet.cell(row=row_idx, column=1).value,
                    'speaker': sheet.cell(row=row_idx, column=2).value if sheet.max_column >= 2 else None,
                    'original': src,
                    'transliterated': romanized,
                    'status': status,
                })

    wb.save(out_xlsx)
    with open(out_jsonl, 'w', encoding='utf-8') as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + '\n')
    with open(out_xlsx + '.done', 'w') as fh:
        fh.write(f'{time.time()}\n{cells_done} cells, {failed} failed\n')

    return {'file': rel, 'skipped': False, 'cells': cells_done, 'failed': failed,
            'api_calls': translator.calls}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='in_dir', required=True)
    ap.add_argument('--out', dest='out_dir', required=True)
    ap.add_argument('--root', default='', help='path root for the mirrored output tree')
    ap.add_argument('--workers', type=int, default=6, help='workbooks in parallel')
    ap.add_argument('--batch-size', type=int, default=12, help='cells per API call')
    ap.add_argument('--limit', type=int, default=0, help='only the first N workbooks (smoke test)')
    ap.add_argument('--force', action='store_true', help='redo files already marked done')
    ap.add_argument('--status', default='', help='write live progress JSON here')
    args = ap.parse_args()

    in_root = args.root or args.in_dir
    files = []
    for dirpath, _dirs, names in os.walk(args.in_dir):
        for n in sorted(names):
            if n.lower().endswith('.xlsx') and not n.startswith('~$'):
                files.append(os.path.join(dirpath, n))
    files.sort()
    if args.limit:
        files = files[:args.limit]

    print(f"{len(files)} workbook(s) under {args.in_dir}", flush=True)
    os.makedirs(args.out_dir, exist_ok=True)
    status_path = args.status or os.path.join(args.out_dir, '_status.json')

    def factory(cache):
        return Translator(batch_size=args.batch_size, cache=cache)

    started = time.time()
    totals = {'files': len(files), 'done': 0, 'skipped': 0, 'cells': 0, 'failed': 0}
    bar = tqdm(total=len(files), unit='file', dynamic_ncols=True)

    def write_status(current=''):
        elapsed = time.time() - started
        rate = totals['done'] / elapsed if elapsed else 0
        left = (totals['files'] - totals['done']) / rate if rate else 0
        with open(status_path, 'w', encoding='utf-8') as fh:
            json.dump({**totals, 'current': current,
                       'elapsed_s': round(elapsed), 'eta_s': round(left),
                       'updated': time.strftime('%Y-%m-%d %H:%M:%S')}, fh, indent=1)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process_workbook, f, in_root, args.out_dir, factory,
                               args.force): f for f in files}
        for fut in as_completed(futures):
            src = futures[fut]
            try:
                res = fut.result()
            except Exception as e:
                print(f"\nERROR {os.path.relpath(src, in_root)}: {e}", flush=True)
                res = {'file': src, 'skipped': False, 'cells': 0, 'failed': 0}
            totals['done'] += 1
            totals['skipped'] += 1 if res.get('skipped') else 0
            totals['cells'] += res.get('cells', 0)
            totals['failed'] += res.get('failed', 0)
            bar.set_postfix(cells=totals['cells'], failed=totals['failed'],
                            skipped=totals['skipped'])
            bar.update(1)
            write_status(res.get('file', ''))
    bar.close()
    write_status('finished')
    print(f"\nFINISHED: {totals['done']} file(s), {totals['cells']} cell(s) transliterated, "
          f"{totals['failed']} failed, {totals['skipped']} already done. "
          f"Output: {args.out_dir}", flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
