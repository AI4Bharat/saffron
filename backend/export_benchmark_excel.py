"""
Excel export for benchmark verification tasks (both rounds).

Produces a review-ready .xlsx that puts the ORIGINAL and the CORRECTED text
side by side, carries every reference field (domain, phenomenon tags, probes
axes, quota class, length bucket, target emotion, the English source sentence),
and keeps every annotator comment — including comments on drafts and skips that
never made it into the final JSONL.

Sheets
------
Annotations       One row per item: original vs corrected raw_text / spoken_form,
                  decision, comment, and who annotated it (latest COMPLETED
                  submission wins, same rule the JSONL export uses). Items nobody
                  finished are still listed, marked "not annotated".
All Submissions   One row per (item, annotator) — every submission including
                  `saved` drafts and `skipped` items, so no comment is lost and
                  disagreements between annotators stay visible.
Rejections        Only the rejected items, with their comments. The triage sheet.
Edits             Only the items whose text an annotator actually changed, with a
                  before/after pair for each changed field.
By Domain         Counts + accept/reject rate per domain.
By Phenomenon     Counts + accept/reject rate per phenomenon tag.
By Language       Counts + accept/reject rate per language.
By Annotator      Per-annotator throughput, verdict split and edit counts.

Usage
-----
    # one batch by DB id
    python export_benchmark_excel.py --test-id 21050 out.xlsx

    # a whole language (all its batches merged)
    python export_benchmark_excel.py --lang hi hi.xlsx

    # every language -> OUTDIR/<lang>.xlsx plus OUTDIR/all_languages.xlsx
    python export_benchmark_excel.py --all exported/

    # the first benchmark round instead of the parallel one
    python export_benchmark_excel.py --round v1 --all exported_v1/

    # both rounds in one workbook
    python export_benchmark_excel.py --round all --lang hi hi_both.xlsx
"""
import os
import re
import sys
import json
import argparse
from datetime import datetime
from collections import defaultdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from application.database import db
from application.models import Test, Rating, Rater
from main import app

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

# round key -> (test_type, task-name prefix)
ROUNDS = {
    'parallel': ('benchmark-parallel', 'benchmark_parallel'),
    'v1': ('benchmark-verification', 'benchmark'),
}

SAFFRON_BASE_URL = os.environ.get('SAFFRON_BASE_URL', 'https://saffron.ai4bharat.org').rstrip('/')

EXCEL_MAX_CELL = 32767

HEADER_FILL = PatternFill('solid', fgColor='1F3864')
HEADER_FONT = Font(color='FFFFFF', bold=True, size=11)
GROUP_FILLS = {
    'meta': PatternFill('solid', fgColor='EAF1F8'),
    'ref': PatternFill('solid', fgColor='FFF6E5'),
    'orig': PatternFill('solid', fgColor='F2F2F2'),
    'corr': PatternFill('solid', fgColor='E9F7EF'),
    'verdict': PatternFill('solid', fgColor='FDEDEC'),
}
ACCEPT_FILL = PatternFill('solid', fgColor='D5F5E3')
REJECT_FILL = PatternFill('solid', fgColor='FADBD8')
EDITED_FILL = PatternFill('solid', fgColor='FCF3CF')
THIN = Side(style='thin', color='D9D9D9')
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def name_token(desc):
    return (desc or '').split(' — ')[0].strip()


def batch_re(prefix):
    # v1's prefix ("benchmark") is a prefix of parallel's ("benchmark_parallel"),
    # so the language group must not be allowed to swallow "parallel".
    return re.compile(rf'^{prefix}_(?P<lang>[a-z]{{2,3}})_batch(?P<n>\d+)$')


def clean(value):
    """Make any value safe for a worksheet cell."""
    if value is None:
        return ''
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        return ', '.join(str(v) for v in value)
    if isinstance(value, dict):
        value = json.dumps(value, ensure_ascii=False)
    text = str(value)
    text = ILLEGAL_CHARACTERS_RE.sub('', text)
    if len(text) > EXCEL_MAX_CELL:
        text = text[:EXCEL_MAX_CELL - 15] + '…[truncated]'
    return text


def pct(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def strip_ref(obj):
    return {k: v for k, v in obj.items() if not k.startswith('_ref_') and k != 'completion_status'}


# --------------------------------------------------------------------------
# data collection
# --------------------------------------------------------------------------

def collect_tests(round_key, lang=None, test_id=None):
    """Return [(test, round_key, lang, batch_no)] ordered by language then batch."""
    wanted = list(ROUNDS) if round_key == 'all' else [round_key]
    rows = []
    for rk in wanted:
        test_type, prefix = ROUNDS[rk]
        rx = batch_re(prefix)
        for t in Test.query.filter_by(test_type=test_type).all():
            if test_id is not None and t.id != test_id:
                continue
            m = rx.match(name_token(t.description))
            if not m:
                continue
            if lang and m.group('lang') != lang:
                continue
            rows.append((t, rk, m.group('lang'), int(m.group('n'))))
    rows.sort(key=lambda r: (r[2], r[1], r[3]))
    return rows


def submissions_for(test_ids):
    """test_id -> item_id -> [Rating], newest first."""
    out = defaultdict(lambda: defaultdict(list))
    if not test_ids:
        return out
    for r in Rating.query.filter(Rating.test_id.in_(test_ids)).all():
        res = r.results_json if isinstance(r.results_json, dict) else {}
        item_id = r.page_no_progress if r.page_no_progress is not None else res.get('id')
        if item_id is None:
            continue
        out[r.test_id][str(item_id)].append(r)
    for per_test in out.values():
        for lst in per_test.values():
            # time_of_submission is non-null in practice, but a NULL must not
            # blow up the sort against a datetime.
            lst.sort(key=lambda r: r.time_of_submission or datetime.min, reverse=True)
    return out


def rater_map():
    return {rt.id: rt for rt in Rater.query.all()}


def latest_completed(ratings):
    return next((r for r in ratings if (r.completion_status or 'completed') == 'completed'), None)


# --------------------------------------------------------------------------
# sheet builders
# --------------------------------------------------------------------------

ANNOTATION_COLUMNS = [
    ('Test ID', 10, 'meta'),
    ('Batch', 30, 'meta'),
    ('Round', 12, 'meta'),
    ('Language', 11, 'meta'),
    ('Item ID', 28, 'meta'),
    ('Source ID', 28, 'meta'),
    ('Suite', 12, 'meta'),
    ('Domain', 22, 'meta'),
    ('Phenomenon Tags', 30, 'meta'),
    ('Probes Axes', 18, 'meta'),
    ('Quota Class', 16, 'meta'),
    ('Length Bucket', 14, 'meta'),
    ('Target Emotion', 15, 'meta'),
    ('English Raw Text', 46, 'ref'),
    ('English Spoken Form', 46, 'ref'),
    ('Original Raw Text', 52, 'orig'),
    ('Original Spoken Form', 52, 'orig'),
    ('Corrected Raw Text', 52, 'corr'),
    ('Corrected Spoken Form', 52, 'corr'),
    ('Raw Text Changed', 15, 'corr'),
    ('Spoken Form Changed', 17, 'corr'),
    ('Decision', 12, 'verdict'),
    ('Comment', 46, 'verdict'),
    ('QA Status', 12, 'verdict'),
    ('Annotator', 20, 'meta'),
    ('Annotator Email', 26, 'meta'),
    ('Status', 14, 'meta'),
    ('Submitted At', 21, 'meta'),
    ('Time Taken (s)', 14, 'meta'),
    ('Other Annotators', 22, 'meta'),
    ('Saffron Link', 34, 'meta'),
]


def style_header(ws, columns):
    for col, (title, width, group) in enumerate(columns, 1):
        c = ws.cell(row=1, column=col, value=title)
        c.fill = HEADER_FILL
        c.font = HEADER_FONT
        c.alignment = Alignment(vertical='center', horizontal='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[1].height = 32
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f'A1:{get_column_letter(len(columns))}1'


def build_annotation_rows(test_rows, subs, raters):
    """Yield one dict per item, latest completed submission merged in."""
    for test, rk, lang, batch_no in test_rows:
        items = test.json_entry if isinstance(test.json_entry, list) else []
        per_item = subs.get(test.id, {})
        for item in items:
            item_id = str(item.get('id'))
            all_subs = per_item.get(item_id, [])
            chosen = latest_completed(all_subs)
            res = chosen.results_json if (chosen and isinstance(chosen.results_json, dict)) else {}
            rt = raters.get(chosen.rater_id) if chosen else None

            orig_raw = item.get('raw_text') or ''
            orig_spoken = item.get('spoken_form') or ''
            corr_raw = res.get('raw_text', orig_raw) if chosen else ''
            corr_spoken = res.get('spoken_form', orig_spoken) if chosen else ''

            others = sorted({
                (raters.get(s.rater_id).name if raters.get(s.rater_id) else f'Rater #{s.rater_id}')
                for s in all_subs
                if not chosen or s.rater_id != chosen.rater_id
            })

            yield {
                'test': test, 'round': rk, 'lang': lang, 'batch_no': batch_no,
                'item': item, 'rating': chosen, 'results': res,
                'orig_raw': orig_raw, 'orig_spoken': orig_spoken,
                'corr_raw': corr_raw, 'corr_spoken': corr_spoken,
                'raw_changed': bool(chosen) and corr_raw != orig_raw,
                'spoken_changed': bool(chosen) and corr_spoken != orig_spoken,
                'decision': (res.get('decision') or '') if chosen else '',
                'comment': (res.get('comments') or res.get('comment') or '') if chosen else '',
                'annotator': rt, 'others': others, 'all_subs': all_subs,
            }


def annotation_row_values(row):
    test, item, chosen, rt = row['test'], row['item'], row['rating'], row['annotator']
    return [
        test.id,
        name_token(test.description),
        row['round'],
        row['lang'],
        item.get('id'),
        item.get('source_id'),
        item.get('suite'),
        item.get('domain'),
        item.get('phenomenon_tags'),
        item.get('probes_axes'),
        item.get('quota_class'),
        item.get('length_bucket'),
        item.get('target_emotion'),
        item.get('_ref_source_raw_text'),
        item.get('_ref_source_spoken_form'),
        row['orig_raw'],
        row['orig_spoken'],
        row['corr_raw'],
        row['corr_spoken'],
        'YES' if row['raw_changed'] else ('' if not chosen else 'no'),
        'YES' if row['spoken_changed'] else ('' if not chosen else 'no'),
        row['decision'],
        row['comment'],
        'verified' if chosen else (item.get('qa_status') or 'pending'),
        rt.name if rt else '',
        rt.email if rt else '',
        (chosen.completion_status or 'completed') if chosen else 'not annotated',
        chosen.time_of_submission.strftime('%Y-%m-%d %H:%M:%S') if (chosen and chosen.time_of_submission) else '',
        round((chosen.time_taken_to_submit or 0) / 1000.0, 1) if chosen else '',
        ', '.join(row['others']),
        f"{SAFFRON_BASE_URL}/{test.id}?task={item.get('id')}",
    ]


def sheet_annotations(wb, rows):
    ws = wb.create_sheet('Annotations')
    style_header(ws, ANNOTATION_COLUMNS)
    dec_col = [c[0] for c in ANNOTATION_COLUMNS].index('Decision') + 1
    raw_col = [c[0] for c in ANNOTATION_COLUMNS].index('Corrected Raw Text') + 1
    spk_col = [c[0] for c in ANNOTATION_COLUMNS].index('Corrected Spoken Form') + 1

    for i, row in enumerate(rows, start=2):
        for col, value in enumerate(annotation_row_values(row), 1):
            c = ws.cell(row=i, column=col, value=clean(value))
            c.alignment = Alignment(vertical='top', wrap_text=True)
            c.border = BORDER
        if row['decision'] == 'accept':
            ws.cell(row=i, column=dec_col).fill = ACCEPT_FILL
        elif row['decision'] == 'reject':
            ws.cell(row=i, column=dec_col).fill = REJECT_FILL
        if row['raw_changed']:
            ws.cell(row=i, column=raw_col).fill = EDITED_FILL
        if row['spoken_changed']:
            ws.cell(row=i, column=spk_col).fill = EDITED_FILL
    return ws


SUBMISSION_COLUMNS = [
    ('Test ID', 10, 'meta'), ('Batch', 30, 'meta'), ('Language', 11, 'meta'),
    ('Item ID', 28, 'meta'), ('Domain', 22, 'meta'), ('Phenomenon Tags', 28, 'meta'),
    ('Annotator', 20, 'meta'), ('Annotator Email', 26, 'meta'),
    ('Status', 13, 'meta'), ('Decision', 12, 'verdict'), ('Comment', 50, 'verdict'),
    ('Original Raw Text', 46, 'orig'), ('Submitted Raw Text', 46, 'corr'),
    ('Original Spoken Form', 46, 'orig'), ('Submitted Spoken Form', 46, 'corr'),
    ('Changed', 12, 'corr'), ('Is Latest Completed', 18, 'meta'),
    ('Submitted At', 21, 'meta'), ('Time Taken (s)', 14, 'meta'),
]


def sheet_all_submissions(wb, rows, raters):
    """Every submission by every annotator — drafts and skips included."""
    ws = wb.create_sheet('All Submissions')
    style_header(ws, SUBMISSION_COLUMNS)
    r_i = 2
    for row in rows:
        item, test = row['item'], row['test']
        chosen = row['rating']
        for s in row['all_subs']:
            res = s.results_json if isinstance(s.results_json, dict) else {}
            rt = raters.get(s.rater_id)
            sub_raw = res.get('raw_text', '')
            sub_spoken = res.get('spoken_form', '')
            changed = (sub_raw != row['orig_raw']) or (sub_spoken != row['orig_spoken'])
            values = [
                test.id, name_token(test.description), row['lang'], item.get('id'),
                item.get('domain'), item.get('phenomenon_tags'),
                rt.name if rt else f'Rater #{s.rater_id}', rt.email if rt else '',
                s.completion_status or 'completed',
                res.get('decision') or '',
                res.get('comments') or res.get('comment') or '',
                row['orig_raw'], sub_raw, row['orig_spoken'], sub_spoken,
                'YES' if changed else 'no',
                'YES' if (chosen is not None and s.id == chosen.id) else 'no',
                s.time_of_submission.strftime('%Y-%m-%d %H:%M:%S') if s.time_of_submission else '',
                round((s.time_taken_to_submit or 0) / 1000.0, 1),
            ]
            for col, value in enumerate(values, 1):
                c = ws.cell(row=r_i, column=col, value=clean(value))
                c.alignment = Alignment(vertical='top', wrap_text=True)
                c.border = BORDER
            r_i += 1
    return ws


def sheet_subset(wb, title, rows, predicate):
    ws = wb.create_sheet(title)
    style_header(ws, ANNOTATION_COLUMNS)
    r_i = 2
    for row in rows:
        if not predicate(row):
            continue
        for col, value in enumerate(annotation_row_values(row), 1):
            c = ws.cell(row=r_i, column=col, value=clean(value))
            c.alignment = Alignment(vertical='top', wrap_text=True)
            c.border = BORDER
        r_i += 1
    return ws


SUMMARY_COLUMNS = ['Items', 'Annotated', 'Accepted', 'Rejected', 'Accept %', 'Reject %',
                   'Raw Text Edited', 'Spoken Form Edited', 'Coverage %']


def sheet_summary(wb, title, key_label, buckets):
    """buckets: label -> counter dict."""
    ws = wb.create_sheet(title)
    columns = [(key_label, 30, 'meta')] + [(c, 14, 'meta') for c in SUMMARY_COLUMNS]
    style_header(ws, columns)
    ordered = sorted(buckets.items(), key=lambda kv: (-kv[1]['annotated'], kv[0]))
    for i, (label, c) in enumerate(ordered, start=2):
        values = [
            label, c['items'], c['annotated'], c['accept'], c['reject'],
            pct(c['accept'], c['annotated']), pct(c['reject'], c['annotated']),
            c['edited_raw'], c['edited_spoken'], pct(c['annotated'], c['items']),
        ]
        for col, value in enumerate(values, 1):
            cell = ws.cell(row=i, column=col, value=clean(value))
            cell.border = BORDER
            if col == 1:
                cell.alignment = Alignment(vertical='center', wrap_text=True)
    # Totals row
    total = _new_bucket()
    for c in buckets.values():
        for k in total:
            total[k] += c[k]
    r = len(ordered) + 2
    values = [
        'TOTAL', total['items'], total['annotated'], total['accept'], total['reject'],
        pct(total['accept'], total['annotated']), pct(total['reject'], total['annotated']),
        total['edited_raw'], total['edited_spoken'], pct(total['annotated'], total['items']),
    ]
    for col, value in enumerate(values, 1):
        cell = ws.cell(row=r, column=col, value=clean(value))
        cell.font = Font(bold=True)
        cell.border = BORDER
    return ws


def _new_bucket():
    return {'items': 0, 'annotated': 0, 'accept': 0, 'reject': 0,
            'edited_raw': 0, 'edited_spoken': 0}


def tally(rows, key_fn):
    """key_fn returns a label or a list of labels for a row."""
    buckets = defaultdict(_new_bucket)
    for row in rows:
        labels = key_fn(row)
        if labels is None:
            continue
        if not isinstance(labels, (list, tuple)):
            labels = [labels]
        if not labels:
            labels = ['(none)']
        for label in labels:
            b = buckets[str(label)]
            b['items'] += 1
            if row['rating'] is None:
                continue
            b['annotated'] += 1
            if row['decision'] == 'accept':
                b['accept'] += 1
            elif row['decision'] == 'reject':
                b['reject'] += 1
            if row['raw_changed']:
                b['edited_raw'] += 1
            if row['spoken_changed']:
                b['edited_spoken'] += 1
    return buckets


def sheet_annotators(wb, rows, raters):
    ws = wb.create_sheet('By Annotator')
    columns = [
        ('Annotator', 24, 'meta'), ('Email', 28, 'meta'), ('Completed', 12, 'meta'),
        ('Saved (draft)', 14, 'meta'), ('Skipped', 11, 'meta'), ('Accepted', 11, 'meta'),
        ('Rejected', 11, 'meta'), ('Accept %', 11, 'meta'), ('Edited Items', 13, 'meta'),
        ('Comments Written', 17, 'meta'), ('Avg Time / Item (s)', 19, 'meta'),
        ('Languages', 26, 'meta'),
    ]
    style_header(ws, columns)

    stats = defaultdict(lambda: {
        'completed': 0, 'saved': 0, 'skipped': 0, 'accept': 0, 'reject': 0,
        'edited': 0, 'comments': 0, 'time': 0.0, 'timed': 0, 'langs': set()})
    for row in rows:
        for s in row['all_subs']:
            res = s.results_json if isinstance(s.results_json, dict) else {}
            st = stats[s.rater_id]
            status = s.completion_status or 'completed'
            if status in ('completed', 'saved', 'skipped'):
                st[status] += 1
            if status == 'completed':
                if res.get('decision') == 'accept':
                    st['accept'] += 1
                elif res.get('decision') == 'reject':
                    st['reject'] += 1
                if res.get('raw_text', row['orig_raw']) != row['orig_raw'] or \
                        res.get('spoken_form', row['orig_spoken']) != row['orig_spoken']:
                    st['edited'] += 1
            if (res.get('comments') or res.get('comment') or '').strip():
                st['comments'] += 1
            if s.time_taken_to_submit:
                st['time'] += s.time_taken_to_submit / 1000.0
                st['timed'] += 1
            st['langs'].add(row['lang'])

    ordered = sorted(stats.items(), key=lambda kv: -kv[1]['completed'])
    for i, (rater_id, st) in enumerate(ordered, start=2):
        rt = raters.get(rater_id)
        verdicts = st['accept'] + st['reject']
        values = [
            rt.name if rt else f'Rater #{rater_id}', rt.email if rt else '',
            st['completed'], st['saved'], st['skipped'], st['accept'], st['reject'],
            pct(st['accept'], verdicts), st['edited'], st['comments'],
            round(st['time'] / st['timed'], 1) if st['timed'] else 0,
            ', '.join(sorted(st['langs'])),
        ]
        for col, value in enumerate(values, 1):
            c = ws.cell(row=i, column=col, value=clean(value))
            c.border = BORDER
    return ws


def sheet_overview(wb, rows, test_rows):
    ws = wb.create_sheet('Overview', 0)
    ws.column_dimensions['A'].width = 34
    ws.column_dimensions['B'].width = 60

    total = len(rows)
    annotated = sum(1 for r in rows if r['rating'])
    accepted = sum(1 for r in rows if r['decision'] == 'accept')
    rejected = sum(1 for r in rows if r['decision'] == 'reject')
    edited = sum(1 for r in rows if r['raw_changed'] or r['spoken_changed'])
    commented = sum(1 for r in rows if (r['comment'] or '').strip())
    langs = sorted({r['lang'] for r in rows})
    rounds = sorted({r['round'] for r in rows})

    lines = [
        ('Benchmark verification export', ''),
        ('', ''),
        ('Rounds', ', '.join(rounds)),
        ('Languages', ', '.join(langs)),
        ('Batches (Test rows)', len(test_rows)),
        ('', ''),
        ('Total items', total),
        ('Annotated (completed)', f'{annotated}  ({pct(annotated, total)}%)'),
        ('Accepted', f'{accepted}  ({pct(accepted, annotated)}% of annotated)'),
        ('Rejected', f'{rejected}  ({pct(rejected, annotated)}% of annotated)'),
        ('Items with edited text', f'{edited}  ({pct(edited, annotated)}% of annotated)'),
        ('Items with a comment', commented),
        ('', ''),
        ('Sheet guide', ''),
        ('  Annotations', 'One row per item — original vs corrected, decision, comment.'),
        ('  All Submissions', 'Every submission by every annotator, drafts and skips included.'),
        ('  Rejections', 'Rejected items only, with comments.'),
        ('  Edits', 'Items whose text an annotator changed.'),
        ('  By Domain / Phenomenon / Language', 'Accept-reject and edit rates per bucket.'),
        ('  By Annotator', 'Per-annotator throughput and verdict split.'),
    ]
    for i, (k, v) in enumerate(lines, start=1):
        a = ws.cell(row=i, column=1, value=clean(k))
        b = ws.cell(row=i, column=2, value=clean(v))
        b.alignment = Alignment(vertical='top', wrap_text=True)
        if i == 1 or k == 'Sheet guide':
            a.font = Font(bold=True, size=14 if i == 1 else 12, color='1F3864')
        elif k and not k.startswith('  '):
            a.font = Font(bold=True)
    return ws


def build_workbook(test_rows, subs, raters):
    rows = list(build_annotation_rows(test_rows, subs, raters))
    wb = Workbook()
    wb.remove(wb.active)

    sheet_annotations(wb, rows)
    sheet_all_submissions(wb, rows, raters)
    sheet_subset(wb, 'Rejections', rows, lambda r: r['decision'] == 'reject')
    sheet_subset(wb, 'Edits', rows, lambda r: r['raw_changed'] or r['spoken_changed'])
    sheet_summary(wb, 'By Domain', 'Domain', tally(rows, lambda r: r['item'].get('domain') or '(none)'))
    sheet_summary(wb, 'By Phenomenon', 'Phenomenon Tag',
                  tally(rows, lambda r: list(r['item'].get('phenomenon_tags') or []) or ['(none)']))
    sheet_summary(wb, 'By Language', 'Language', tally(rows, lambda r: r['lang']))
    sheet_annotators(wb, rows, raters)
    sheet_overview(wb, rows, test_rows)
    wb.active = 0
    return wb, rows


def save(wb, path):
    out_dir = os.path.dirname(os.path.abspath(path))
    os.makedirs(out_dir, exist_ok=True)
    wb.save(path)


def main():
    ap = argparse.ArgumentParser(description='Excel export of benchmark verification annotations')
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--test-id', type=int, help='Export a single batch by DB Test id')
    g.add_argument('--lang', help='Export a whole language (all its batches merged)')
    g.add_argument('--all', metavar='OUTDIR', help='Export every language to OUTDIR/<lang>.xlsx')
    ap.add_argument('output', nargs='?', help='Output .xlsx path (for --test-id / --lang)')
    ap.add_argument('--round', default='parallel', choices=['parallel', 'v1', 'all'],
                    help="Which benchmark round to export (default: parallel)")
    ap.add_argument('--combined', action='store_true',
                    help='With --all, also write OUTDIR/all_languages.xlsx (default: on)')
    ap.add_argument('--no-combined', dest='combined', action='store_false')
    ap.set_defaults(combined=True)
    args = ap.parse_args()

    with app.app_context():
        raters = rater_map()

        if args.test_id is not None or args.lang:
            if not args.output:
                ap.error('output path is required with --test-id / --lang')
            test_rows = collect_tests(
                args.round,
                lang=args.lang.strip().lower() if args.lang else None,
                test_id=args.test_id,
            )
            if not test_rows:
                target = f'test id {args.test_id}' if args.test_id else f"language '{args.lang}'"
                print(f"Error: no '{args.round}' benchmark batches found for {target}.")
                sys.exit(1)
            subs = submissions_for([t.id for t, *_ in test_rows])
            wb, rows = build_workbook(test_rows, subs, raters)
            save(wb, args.output)
            ann = sum(1 for r in rows if r['rating'])
            print(f'Wrote {len(rows)} items ({ann} annotated) from {len(test_rows)} batch(es) -> {args.output}')
            return

        # --all
        outdir = args.all
        test_rows = collect_tests(args.round)
        if not test_rows:
            print(f"Error: no '{args.round}' benchmark tasks found in the database.")
            sys.exit(1)
        subs = submissions_for([t.id for t, *_ in test_rows])

        by_lang = defaultdict(list)
        for tr in test_rows:
            by_lang[tr[2]].append(tr)
        for lang, lang_rows in sorted(by_lang.items()):
            wb, rows = build_workbook(lang_rows, subs, raters)
            path = os.path.join(outdir, f'{lang}.xlsx')
            save(wb, path)
            ann = sum(1 for r in rows if r['rating'])
            print(f'{lang}: {len(rows)} items ({ann} annotated), {len(lang_rows)} batch(es) -> {path}')

        if args.combined:
            wb, rows = build_workbook(test_rows, subs, raters)
            path = os.path.join(outdir, 'all_languages.xlsx')
            save(wb, path)
            ann = sum(1 for r in rows if r['rating'])
            print(f'ALL: {len(rows)} items ({ann} annotated), {len(test_rows)} batch(es) -> {path}')


if __name__ == '__main__':
    main()
