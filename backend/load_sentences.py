"""Load benchmark SENTENCE translation-correction tasks into saffron.

Builds `sentence-correction` Test batches (250 tasks each) from the dashboard
sentence corpora, aligning each translated sentence with its English source:

  - sentences_ncert_<lang>.jsonl       -> level "Secondary - Senior Secondary"
  - sentences_elementary_<lang>.jsonl  -> level "Elementary"
  - sentences_<lang>.txt               -> level "Combined"   (flat Advanced tier)

Each task item: {id, target_language, level, subject, grade_bucket, text, text_en}.
Idempotent: a batch whose exact description already exists is skipped, so re-running
only adds what is missing. Never deletes anything.

Usage (run inside the saffron backend venv):
    python load_sentences.py --dry-run                 # report only, write nothing
    python load_sentences.py                           # all languages, all levels
    python load_sentences.py --languages hindi,odia    # subset
    python load_sentences.py --levels ncert            # one level (ncert|elementary|combined)
"""
import os, re, sys, json, argparse

sys.path.append('/root/saffron/backend')
os.chdir('/root/saffron/backend')
from main import app
from application.database import db
from application.models import Test

DASH = '/data/dashboard'
BATCH = 250
ID_BASE = 20000  # sentence Test ids live here, well clear of existing batches (<=10029)

LANGUAGES = ["bengali", "gujarati", "hindi", "kannada", "malayalam",
             "marathi", "odia", "tamil", "telugu", "urdu"]

# level key -> (english file stem, translated file template, jsonl?, level label, desc prefix)
LEVELS = {
    "ncert":      ("sentences_ncert",       "sentences_ncert_{lang}.jsonl",      True,
                   "Secondary - Senior Secondary", "Secondary - Senior Secondary {Lang} Sentences"),
    "elementary": ("sentences_elementary",  "sentences_elementary_{lang}.jsonl", True,
                   "Elementary", "Elementary {Lang} Sentences"),
    "combined":   ("sentences",             "sentences_{lang}.txt",              False,
                   "Combined", "Combined {Lang} Sentences"),
}

_SENT_RE = re.compile(r"^\s*\[(\d+)\]\s*\[([^\]]*)\]\s*[—–-]\s*(.*)$", re.DOTALL)


def load_jsonl(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                pattern = r'(?<!\\)\\(times|theta|tau|to|text|tfrac|triangle|frac|phi|varphi|forall|beta|binom|bar|bullet|bot|begin|tilde|tan|top|textrm|textbf|textit)\b'
                fixed_line = re.sub(pattern, r'\\\\\1', line)
                out.append(json.loads(fixed_line))
    return out


def parse_txt(path):
    """seq(str) -> {'subject', 'text'} for a flat [seq] [SUBJECT] — text file."""
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = _SENT_RE.match(line)
            if m:
                seq, subject, text = m.group(1), m.group(2).strip().title(), m.group(3).strip()
                out[seq] = {"subject": subject, "text": text}
    return out


def build_items(level_key, lang):
    eng_stem, tmpl, is_jsonl, level_label, _ = LEVELS[level_key]
    trans_path = os.path.join(DASH, tmpl.format(lang=lang))
    if not os.path.exists(trans_path):
        return None
    items = []
    if is_jsonl:
        eng_path = os.path.join(DASH, eng_stem + ".jsonl")
        eng_map = {r.get("id"): r for r in load_jsonl(eng_path)}
        for r in load_jsonl(trans_path):
            rid = r.get("id")
            text = (r.get("text") or "").strip()
            if not rid or not text:
                continue
            en = eng_map.get(rid) or {}
            items.append({
                "id": rid,
                "target_language": lang,
                "level": level_label,
                "subject": (r.get("subject") or en.get("subject") or "").strip(),
                "grade_bucket": (r.get("grade_bucket") or en.get("grade_bucket") or "").strip(),
                "text": text,
                "text_en": (en.get("text") or "").strip(),
            })
    else:
        eng_path = os.path.join(DASH, eng_stem + ".txt")
        eng_map = parse_txt(eng_path)
        for seq, tr in parse_txt(trans_path).items():
            if not tr["text"]:
                continue
            en = eng_map.get(seq, {})
            items.append({
                "id": f"sent-{seq}",
                "target_language": lang,
                "level": level_label,
                "subject": tr["subject"] or en.get("subject", ""),
                "grade_bucket": "",
                "text": tr["text"],
                "text_en": en.get("text", ""),
            })
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--languages", default=",".join(LANGUAGES))
    ap.add_argument("--levels", default=",".join(LEVELS.keys()))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    langs = [l.strip().lower() for l in args.languages.split(",") if l.strip()]
    levels = [l.strip().lower() for l in args.levels.split(",") if l.strip()]

    with app.app_context():
        existing_desc = {t.description for t in Test.query.with_entities(Test.description).all()}
        next_id = max(ID_BASE, (db.session.query(db.func.max(Test.id)).scalar() or 0) + 1)

        created, skipped, total_tasks = 0, 0, 0
        for level_key in levels:
            _, _, _, _, prefix_tmpl = LEVELS[level_key]
            for lang in langs:
                items = build_items(level_key, lang)
                if items is None:
                    print(f"  [skip] no file for {level_key}/{lang}")
                    continue
                prefix = prefix_tmpl.format(Lang=lang.capitalize())
                n = len(items)
                nb = (n + BATCH - 1) // BATCH
                for i in range(nb):
                    chunk = items[i * BATCH:(i + 1) * BATCH]
                    start, end = i * BATCH + 1, i * BATCH + len(chunk)
                    desc = f"{prefix} - Part {i+1} (Tasks {start} to {end})"
                    if desc in existing_desc:
                        skipped += 1
                        continue
                    total_tasks += len(chunk)
                    if args.dry_run:
                        print(f"  [dry] would create id={next_id} '{desc}'  ({len(chunk)} tasks)")
                    else:
                        db.session.add(Test(id=next_id, test_type="sentence-correction",
                                            description=desc, json_entry=chunk))
                        db.session.commit()
                        print(f"  created id={next_id} '{desc}'  ({len(chunk)} tasks)")
                    existing_desc.add(desc)
                    next_id += 1
                    created += 1
        print(f"\n{'DRY-RUN ' if args.dry_run else ''}done: {created} batch(es) "
              f"{'to create' if args.dry_run else 'created'}, {skipped} already existed, "
              f"{total_tasks} tasks.")


if __name__ == "__main__":
    main()
