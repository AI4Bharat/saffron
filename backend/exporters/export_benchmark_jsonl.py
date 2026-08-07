"""Export annotated benchmark verification tasks back to JSONL."""
import os
import sys
import json
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating
from main import app

TEST_TYPE = "benchmark-verification"


def _name_token(desc):
    return (desc or "").split(" — ")[0].strip()


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


def export_test(test, out_lines):
    """Append this test's items (annotations merged) to out_lines."""
    items = test.json_entry
    if not isinstance(items, list):
        print(f"[WARN] Test #{test.id} json_entry is not a list; skipping.")
        return (0, 0)

    latest = _latest_completed_by_item(test.id)
    n_annotated = 0

    for item in items:
        out = json.loads(json.dumps(item))  # deep copy, preserves key order
        item_id = str(out.get('id'))
        res = latest.get(item_id)
        if isinstance(res, dict):
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
        out_lines.append(out)

    return (len(items), n_annotated)


def write_jsonl(path, lines):
    out_dir = os.path.dirname(path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as fh:
        for obj in lines:
            fh.write(json.dumps(obj, ensure_ascii=False) + '\n')


def tests_for_lang(lang):
    """All benchmark batch Tests for a language, ordered by batch number."""
    prefix = f"benchmark_{lang}_batch"
    rows = []
    for t in Test.query.filter_by(test_type=TEST_TYPE).all():
        name = _name_token(t.description)
        if name.startswith(prefix):
            try:
                n = int(name[len(prefix):])
            except ValueError:
                n = 0
            rows.append((n, t))
    rows.sort(key=lambda x: x[0])
    return [t for _, t in rows]


def main():
    ap = argparse.ArgumentParser(description="Export benchmark annotations to JSONL")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--test-id', type=int, help='Export a single batch by DB Test id')
    g.add_argument('--lang', help='Export a whole language (all batches merged)')
    g.add_argument('--all', metavar='OUTDIR', help='Export every language to OUTDIR/<lang>.jsonl')
    ap.add_argument('output', nargs='?', help='Output path (file for --test-id/--lang)')
    args = ap.parse_args()

    with app.app_context():
        if args.test_id is not None:
            if not args.output:
                ap.error('output path is required with --test-id')
            test = db.session.get(Test, args.test_id)
            if not test or test.test_type != TEST_TYPE:
                print(f"Error: Test #{args.test_id} is not a benchmark-verification task.")
                sys.exit(1)
            lines = []
            n, ann = export_test(test, lines)
            write_jsonl(args.output, lines)
            print(f"Exported {n} items ({ann} annotated) from Test #{test.id} -> {args.output}")

        elif args.lang:
            lang = args.lang.strip().lower()
            if not args.output:
                ap.error('output path is required with --lang')
            tests = tests_for_lang(lang)
            if not tests:
                print(f"Error: no benchmark batches found for language '{lang}'.")
                sys.exit(1)
            lines, total, total_ann = [], 0, 0
            for t in tests:
                n, ann = export_test(t, lines)
                total += n
                total_ann += ann
                print(f"  #{t.id} {_name_token(t.description)}: {n} items, {ann} annotated")
            write_jsonl(args.output, lines)
            print(f"Exported {total} items ({total_ann} annotated) across {len(tests)} batch(es) -> {args.output}")

        else:  # --all
            outdir = args.all
            langs = sorted({
                _name_token(t.description).split('_')[1]
                for t in Test.query.filter_by(test_type=TEST_TYPE).all()
                if _name_token(t.description).startswith('benchmark_')
            })
            if not langs:
                print("Error: no benchmark tasks found in the database.")
                sys.exit(1)
            for lang in langs:
                tests = tests_for_lang(lang)
                lines, total, total_ann = [], 0, 0
                for t in tests:
                    n, ann = export_test(t, lines)
                    total += n
                    total_ann += ann
                path = os.path.join(outdir, f"{lang}.jsonl")
                write_jsonl(path, lines)
                print(f"{lang}: {total} items ({total_ann} annotated), {len(tests)} batch(es) -> {path}")


if __name__ == "__main__":
    main()
