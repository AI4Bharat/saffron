"""
Export annotated PARALLEL benchmark verification tasks (test_type
``benchmark-parallel``) back to JSONL.

Every output line is the EXACT original input object — all fields preserved, in
their original order, including ``domain``, ``phenomenon_tags``, ``probes_axes``,
``quota_class``, ``source_id`` and the rest — with only the annotation results
merged in for items an annotator completed:

    qa_status   -> true            (item has been verified)
    raw_text    -> edited value    (annotator's correction, if any)
    spoken_form -> edited value    (annotator's correction, if any)
    decision    -> "accept" | "reject"
    comment     -> annotator's comment   (only added when non-empty)

The loader attaches the English source sentence to each item under `_ref_*` keys
for the annotation UI; those (and any runtime-only key such as
``completion_status``) are stripped here, so a no-annotation export is a lossless
round-trip of the input file.

Items nobody completed are emitted UNCHANGED (``qa_status`` stays "pending"), so a
partially-annotated batch still round-trips cleanly. If several annotators rated
the same item, the LATEST completed submission wins.

Usage:
    # one batch by DB id
    python export_benchmark_parallel_jsonl.py --test-id 21050 out.jsonl

    # a whole language: merges benchmark_parallel_<lang>_batch1..N in order
    python export_benchmark_parallel_jsonl.py --lang hi hi.out.jsonl

    # every language -> one <lang>.jsonl per language in a directory
    python export_benchmark_parallel_jsonl.py --all exported/

    # also write a domain / phenomenon-tag accept-reject breakdown
    python export_benchmark_parallel_jsonl.py --all exported/ --summary exported/summary.json
"""
import os
import re
import sys
import json
import argparse
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating
from main import app

TEST_TYPE = "benchmark-parallel"
NAME_PREFIX = "benchmark_parallel"
NAME_RE = re.compile(rf"^{NAME_PREFIX}_(?P<lang>[a-z]{{2,3}})_batch(?P<n>\d+)$")

# Keys the app adds at load/serve time that are NOT part of the source format.
RUNTIME_KEYS = ("completion_status",)


def _name_token(desc):
    return (desc or "").split(" — ")[0].strip()


def _strip_runtime_keys(obj):
    """Drop the UI-only reference keys so the line matches the input format."""
    return {
        k: v for k, v in obj.items()
        if not k.startswith("_ref_") and k not in RUNTIME_KEYS
    }


def _latest_completed_by_item(test_id):
    """Map item-id -> results_json of the latest COMPLETED rating for that item."""
    ratings = (
        Rating.query
        .filter_by(test_id=test_id)
        .filter(Rating.completion_status == 'completed')
        .all()
    )
    latest = {}
    for r in ratings:
        res = r.results_json
        item_id = None
        if r.page_no_progress is not None:
            item_id = r.page_no_progress
        elif isinstance(res, dict) and 'id' in res:
            item_id = res['id']
        if item_id is None:
            continue
        item_id = str(item_id)
        if item_id not in latest or r.time_of_submission > latest[item_id][0]:
            latest[item_id] = (r.time_of_submission, res)
    return {k: v[1] for k, v in latest.items()}


class Stats:
    """Accept/reject and edit counts, overall and per domain / phenomenon tag."""

    def __init__(self):
        self.total = 0
        self.annotated = 0
        self.by_decision = defaultdict(int)
        self.edited_raw = 0
        self.edited_spoken = 0
        self.by_domain = defaultdict(lambda: defaultdict(int))
        self.by_phenomenon = defaultdict(lambda: defaultdict(int))
        self.by_lang = defaultdict(lambda: defaultdict(int))

    def record(self, original, out, annotated):
        self.total += 1
        domain = original.get('domain') or 'unknown'
        lang = original.get('lang') or 'unknown'
        tags = original.get('phenomenon_tags') or ['none']

        self.by_domain[domain]['total'] += 1
        self.by_lang[lang]['total'] += 1
        for t in tags:
            self.by_phenomenon[t]['total'] += 1

        if not annotated:
            return

        self.annotated += 1
        decision = out.get('decision') or 'unspecified'
        self.by_decision[decision] += 1
        self.by_domain[domain]['annotated'] += 1
        self.by_domain[domain][decision] += 1
        self.by_lang[lang]['annotated'] += 1
        self.by_lang[lang][decision] += 1
        for t in tags:
            self.by_phenomenon[t]['annotated'] += 1
            self.by_phenomenon[t][decision] += 1

        if out.get('raw_text') != original.get('raw_text'):
            self.edited_raw += 1
            self.by_domain[domain]['edited_raw'] += 1
            for t in tags:
                self.by_phenomenon[t]['edited_raw'] += 1
        if out.get('spoken_form') != original.get('spoken_form'):
            self.edited_spoken += 1
            self.by_domain[domain]['edited_spoken'] += 1
            for t in tags:
                self.by_phenomenon[t]['edited_spoken'] += 1

    def as_dict(self):
        def unpack(d):
            return {k: dict(v) for k, v in sorted(d.items())}
        return {
            'total_items': self.total,
            'annotated_items': self.annotated,
            'decisions': dict(sorted(self.by_decision.items())),
            'edited_raw_text': self.edited_raw,
            'edited_spoken_form': self.edited_spoken,
            'by_language': unpack(self.by_lang),
            'by_domain': unpack(self.by_domain),
            'by_phenomenon_tag': unpack(self.by_phenomenon),
        }

    def print_report(self):
        print("\n--- Annotation summary ---")
        print(f"  items: {self.total}   annotated: {self.annotated}   "
              f"accept: {self.by_decision.get('accept', 0)}   reject: {self.by_decision.get('reject', 0)}")
        print(f"  edited raw_text: {self.edited_raw}   edited spoken_form: {self.edited_spoken}")
        rows = [(d, c) for d, c in self.by_domain.items() if c.get('annotated')]
        if rows:
            print("\n  By domain (annotated / accept / reject / edited):")
            for d, c in sorted(rows, key=lambda x: -x[1]['annotated']):
                print(f"    {d:<24} {c.get('annotated', 0):>5} / {c.get('accept', 0):>5} / "
                      f"{c.get('reject', 0):>5} / {c.get('edited_raw', 0) + c.get('edited_spoken', 0):>5}")
        rows = [(t, c) for t, c in self.by_phenomenon.items() if c.get('annotated')]
        if rows:
            print("\n  By phenomenon tag (annotated / accept / reject / edited):")
            for t, c in sorted(rows, key=lambda x: -x[1]['annotated']):
                print(f"    {t:<24} {c.get('annotated', 0):>5} / {c.get('accept', 0):>5} / "
                      f"{c.get('reject', 0):>5} / {c.get('edited_raw', 0) + c.get('edited_spoken', 0):>5}")


def export_test(test, out_lines, stats=None):
    """Append this test's items (annotations merged) to out_lines.

    Returns (n_items, n_annotated).
    """
    items = test.json_entry
    if not isinstance(items, list):
        print(f"[WARN] Test #{test.id} json_entry is not a list; skipping.")
        return (0, 0)

    latest = _latest_completed_by_item(test.id)
    n_annotated = 0

    for item in items:
        original = _strip_runtime_keys(item)
        out = json.loads(json.dumps(original))  # deep copy, preserves key order
        item_id = str(out.get('id'))
        res = latest.get(item_id)
        annotated = isinstance(res, dict)
        if annotated:
            n_annotated += 1
            out['qa_status'] = True
            if 'raw_text' in res:
                out['raw_text'] = res['raw_text']
            if 'spoken_form' in res:
                out['spoken_form'] = res['spoken_form']
            if res.get('decision'):
                out['decision'] = res['decision']
            comment = (res.get('comments') or res.get('comment') or '')
            if isinstance(comment, str) and comment.strip():
                out['comment'] = comment.strip()
        if stats is not None:
            stats.record(original, out, annotated)
        out_lines.append(out)

    return (len(items), n_annotated)


def write_jsonl(path, lines):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + '\n')


def all_tests():
    return Test.query.filter_by(test_type=TEST_TYPE).all()


def tests_for_lang(lang):
    """All parallel benchmark batch Tests for a language, ordered by batch number."""
    rows = []
    for t in all_tests():
        m = NAME_RE.match(_name_token(t.description))
        if m and m.group('lang') == lang:
            rows.append((int(m.group('n')), t))
    rows.sort(key=lambda x: x[0])
    return [t for _, t in rows]


def available_langs():
    langs = set()
    for t in all_tests():
        m = NAME_RE.match(_name_token(t.description))
        if m:
            langs.add(m.group('lang'))
    return sorted(langs)


def write_summary(path, stats):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(stats.as_dict(), fh, ensure_ascii=False, indent=2)
    print(f"\nSummary written -> {path}")


def main():
    ap = argparse.ArgumentParser(description="Export parallel benchmark annotations to JSONL")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--test-id', type=int, help='Export a single batch by DB Test id')
    g.add_argument('--lang', help='Export a whole language (all batches merged)')
    g.add_argument('--all', metavar='OUTDIR', help='Export every language to OUTDIR/<lang>.jsonl')
    ap.add_argument('output', nargs='?', help='Output path (file for --test-id/--lang)')
    ap.add_argument('--summary', metavar='PATH',
                    help='Also write a domain / phenomenon-tag accept-reject breakdown as JSON')
    args = ap.parse_args()

    stats = Stats()

    with app.app_context():
        if args.test_id is not None:
            if not args.output:
                ap.error('output path is required with --test-id')
            test = db.session.get(Test, args.test_id)
            if not test or test.test_type != TEST_TYPE:
                print(f"Error: Test #{args.test_id} is not a {TEST_TYPE} task.")
                sys.exit(1)
            lines = []
            n, ann = export_test(test, lines, stats)
            write_jsonl(args.output, lines)
            print(f"Exported {n} items ({ann} annotated) from Test #{test.id} -> {args.output}")

        elif args.lang:
            lang = args.lang.strip().lower()
            if not args.output:
                ap.error('output path is required with --lang')
            tests = tests_for_lang(lang)
            if not tests:
                print(f"Error: no {TEST_TYPE} batches found for language '{lang}'.")
                sys.exit(1)
            lines, total, total_ann = [], 0, 0
            for t in tests:
                n, ann = export_test(t, lines, stats)
                total += n
                total_ann += ann
                print(f"  #{t.id} {_name_token(t.description)}: {n} items, {ann} annotated")
            write_jsonl(args.output, lines)
            print(f"Exported {total} items ({total_ann} annotated) across {len(tests)} batch(es) -> {args.output}")

        else:  # --all
            outdir = args.all
            langs = available_langs()
            if not langs:
                print(f"Error: no {TEST_TYPE} tasks found in the database.")
                sys.exit(1)
            for lang in langs:
                tests = tests_for_lang(lang)
                lines, total, total_ann = [], 0, 0
                for t in tests:
                    n, ann = export_test(t, lines, stats)
                    total += n
                    total_ann += ann
                path = os.path.join(outdir, f"{lang}.jsonl")
                write_jsonl(path, lines)
                print(f"{lang}: {total} items ({total_ann} annotated), {len(tests)} batch(es) -> {path}")

        stats.print_report()
        if args.summary:
            write_summary(args.summary, stats)


if __name__ == "__main__":
    main()
