"""MDFS scores for the dashboard: what each annotator gave, side by side.

Every figure here comes from pool_annotation, one row per annotator, because
that is where each person's own scores live. The copy on the item
(extra_json['results']) is only ever the last submitter's, so with three
annotators it would under-report by two thirds -- it is deliberately not used.

Admin-only. Annotators never reach these routes; their own view shows only
their own answers.
"""
import csv
import io
from collections import defaultdict
from statistics import mean, pstdev

from flask import jsonify, request

from main import app
from application.database import db
from application.models import PoolAnnotation, PoolItem, PoolTask, Rater
from application.pool_common import (MDFS_DIMENSIONS, annotations_target,
                                     csv_response, _ist_stamp)
from application.pool_api import _admin_pool_team
from application.views import token_required

TASK_TYPE = 'audio-mdfs'


# Every column of benchmark_final_7lang.csv, in its original order. These ride
# on the item and are reported here; the annotator's page never sees them --
# E/P/S/Pa and tagged_text would hand a rater the answer.
SOURCE_META = ('clip_id', 'language', 'para_id', 'profile_id', 'E', 'P', 'S', 'Pa',
               'tagged_text', 'n_tags', 'tagged_words', 'paragraph_words',
               'tts_audio_path', 'tts_duration_sec', 'vc_audio_path', 'ref_id',
               'ref_audio_path', 'ref_age_group', 'ref_student_class',
               'ref_gender', 'tts_model', 'audio_status', 'qc_status',
               'source_csv')

def _rows(team, language=None, only_complete=False):
    """(item, [annotations]) for every rated MDFS prompt, newest task first."""
    q = (db.session.query(PoolItem)
         .filter(PoolItem.team_id == team.id, PoolItem.task_type == TASK_TYPE))
    if language:
        q = q.filter(PoolItem.language == language)
    items = {i.id: i for i in q.all()}
    if not items:
        return {}, {}

    anns = defaultdict(list)
    for a in (PoolAnnotation.query
              .filter(PoolAnnotation.item_id.in_(list(items)),
                      PoolAnnotation.status == 'completed')
              .order_by(PoolAnnotation.completed_at).all()):
        if isinstance(a.results_json, dict):
            anns[a.item_id].append(a)

    if only_complete:
        target = annotations_target(team, PoolTask.query.filter_by(
            team_id=team.id, task_type=TASK_TYPE).first())
        items = {k: v for k, v in items.items() if len(anns.get(k, [])) >= target}
    return items, anns


def _spread(values):
    """How far apart the annotators were on one dimension."""
    if len(values) < 2:
        return 0.0
    return round(pstdev(values), 2)


def _filters_from_request():
    """The cuts the table and the export both apply, read off the query string."""
    def _f(name, cast, default=None):
        try:
            v = cast(request.args.get(name) or 0)
            return v or default
        except (TypeError, ValueError):
            return default

    return {
        'status': (request.args.get('status') or '').strip().lower(),
        'category': (request.args.get('category') or '').strip().lower() or None,
        'query': (request.args.get('q') or '').strip().lower() or None,
        'rater': _f('annotator', int),
        'min_spread': _f('min_spread', float, 0.0) or 0.0,
        'max_mean': _f('max_mean', float),
    }


def _passes(row, f):
    """Does one assembled row survive the filters?"""
    if f['status'] == 'unrated' and row['answers'] != 0:
        return False
    if f['status'] == 'partial' and not (0 < row['answers'] < row['target']):
        return False
    if f['status'] == 'complete' and row['answers'] < row['target']:
        return False
    if f['category'] and (row['category'] or '').lower() != f['category']:
        return False
    if f['rater'] and not any(a['rater_id'] == f['rater'] for a in row['raters']):
        return False
    if f['min_spread'] and row['spread'] < f['min_spread']:
        return False
    if f['max_mean'] is not None:
        vals = [v for v in row['mean'].values() if isinstance(v, (int, float))]
        # an unrated prompt has no mean, so it cannot satisfy a score cut
        if not vals or (sum(vals) / len(vals)) > f['max_mean']:
            return False
    if f['query']:
        hay = '%s %s' % ((row['text'] or ''), (row['clip_id'] or ''))
        if f['query'] not in hay.lower():
            return False
    return True


@app.route('/api/pool/admin/mdfs/scores', methods=['GET'])
@token_required
def pool_mdfs_scores(current_user):
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    language = (request.args.get('language') or '').strip() or None
    only_complete = request.args.get('complete') in ('1', 'true')
    filters = _filters_from_request()
    try:
        limit = max(1, min(int(request.args.get('limit') or 200), 1000))
    except (TypeError, ValueError):
        limit = 200
    try:
        page = max(1, int(request.args.get('page') or 1))
    except (TypeError, ValueError):
        page = 1

    items, anns = _rows(team, language, only_complete)
    task = PoolTask.query.filter_by(team_id=team.id, task_type=TASK_TYPE).first()
    target = annotations_target(team, task)
    names = {r.id: (r.name or r.email or '#%s' % r.id) for r in Rater.query.all()}

    # per language: how far along, and the averages so far
    per_lang = defaultdict(lambda: {'items': 0, 'rated': 0, 'complete': 0,
                                    'annotations': 0,
                                    'sums': defaultdict(float), 'n': 0})
    rows = []
    for item_id, item in items.items():
        got = anns.get(item_id, [])
        slot = per_lang[item.language or 'Unknown']
        slot['items'] += 1
        slot['annotations'] += len(got)
        if got:
            slot['rated'] += 1
        if len(got) >= target:
            slot['complete'] += 1

        by_rater = []
        for a in got:
            r = a.results_json or {}
            scores = {d: r.get(d) for d in MDFS_DIMENSIONS}
            for d, v in scores.items():
                if isinstance(v, int):
                    slot['sums'][d] += v
            if all(isinstance(v, int) for v in scores.values()):
                slot['n'] += 1
            by_rater.append({
                'rater_id': a.rater_id,
                'annotator': names.get(a.rater_id, ''),
                'scores': scores,
                'comments': (r.get('comments') or ''),
                'submitted_ist': _ist_stamp(a.completed_at) if a.completed_at else '',
                'seconds': round((a.time_taken_ms or 0) / 1000.0, 1),
            })

        means, spreads = {}, {}
        for d in MDFS_DIMENSIONS:
            vals = [x['scores'][d] for x in by_rater if isinstance(x['scores'][d], int)]
            means[d] = round(mean(vals), 2) if vals else None
            spreads[d] = _spread(vals)

        rows.append({
            'item_id': item_id,
            'language': item.language,
            'category': item.category,
            # the whole paragraph: it is what the rating is about
            'text': item.text or '',
            'audio': (item.extra_json or {}).get('audio'),
            'clip_id': (item.extra_json or {}).get('clip_id'),
            'answers': len(by_rater),
            'target': target,
            'raters': by_rater,
            'mean': means,
            # the largest disagreement across the four dimensions
            'spread': max(spreads.values()) if spreads else 0.0,
        })

    rows = [r for r in rows if _passes(r, filters)]

    # most disagreement first: those are the rows worth a human eye
    rows.sort(key=lambda r: (-r['spread'], -r['answers'], r['item_id']))
    total = len(rows)
    start = (page - 1) * limit
    page_rows = rows[start:start + limit]

    languages = []
    for lang, s in sorted(per_lang.items()):
        avg = {d: (round(s['sums'][d] / s['n'], 2) if s['n'] else None)
               for d in MDFS_DIMENSIONS}
        languages.append({
            'language': lang, 'items': s['items'], 'rated': s['rated'],
            'complete': s['complete'], 'annotations': s['annotations'],
            'average': avg,
            'progress': round(100.0 * s['complete'] / s['items'], 1) if s['items'] else 0.0,
        })

    categories = sorted({(i.category or '') for i in items.values() if i.category})
    annotators = sorted(
        ({'rater_id': rid, 'name': names.get(rid, '')}
         for rid in {a.rater_id for lst in anns.values() for a in lst}),
        key=lambda x: x['name'].lower())

    return jsonify({
        'dimensions': list(MDFS_DIMENSIONS),
        'target': target,
        'categories': categories,
        'annotators': annotators,
        'languages': languages,
        'totals': {
            'items': sum(l['items'] for l in languages),
            'rated': sum(l['rated'] for l in languages),
            'complete': sum(l['complete'] for l in languages),
            'annotations': sum(l['annotations'] for l in languages),
        },
        'rows': page_rows,
        'page': page,
        'pages': max(1, (total + limit - 1) // limit),
        'total': total,
    }), 200


@app.route('/api/pool/admin/mdfs/export_csv', methods=['GET'])
@token_required
def pool_mdfs_export_csv(current_user):
    """One row per ANNOTATION, so all three ratings of a prompt are present."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    language = (request.args.get('language') or '').strip() or None
    items, anns = _rows(team, language, request.args.get('complete') in ('1', 'true'))
    names = {r.id: (r.name or '', r.email or '') for r in Rater.query.all()}
    # Same cuts the table applies, so a download matches what is on screen.
    filters = _filters_from_request()
    display = {r.id: (r.name or r.email or '#%s' % r.id) for r in Rater.query.all()}

    header = (['Sr. No.', 'Item ID', 'Clip ID', 'Language', 'Category',
               'Answers', 'Annotator', 'Email']
              + [d.title() for d in MDFS_DIMENSIONS]
              + ['Mean (this rater)', 'Comments', 'Submitted (IST)', 'Seconds',
                 'Audio', 'Text']
              + ['source_' + c for c in SOURCE_META])
    out = [header]
    n = 0
    target_x = annotations_target(team, PoolTask.query.filter_by(
        team_id=team.id, task_type=TASK_TYPE).first())
    for item_id, item in sorted(items.items()):
        got = anns.get(item_id, [])
        # rebuild just enough of the row shape for the shared predicate
        raters_view, spreads = [], {}
        for a in got:
            rj = a.results_json or {}
            raters_view.append({'rater_id': a.rater_id,
                                'scores': {d: rj.get(d) for d in MDFS_DIMENSIONS}})
        means = {}
        for d in MDFS_DIMENSIONS:
            vals = [x['scores'][d] for x in raters_view
                    if isinstance(x['scores'][d], int)]
            means[d] = round(mean(vals), 2) if vals else None
            spreads[d] = _spread(vals)
        probe = {'answers': len(got), 'target': target_x,
                 'category': item.category, 'raters': raters_view,
                 'mean': means, 'spread': max(spreads.values()) if spreads else 0.0,
                 'text': item.text or '',
                 'clip_id': (item.extra_json or {}).get('clip_id', '')}
        if not _passes(probe, filters):
            continue
        for a in got:
            r = a.results_json or {}
            vals = [r.get(d) for d in MDFS_DIMENSIONS]
            nums = [v for v in vals if isinstance(v, int)]
            n += 1
            nm, em = names.get(a.rater_id, ('', ''))
            out.append([n, item_id, (item.extra_json or {}).get('clip_id', ''),
                        item.language, item.category, len(got), nm, em]
                       + vals
                       + [round(mean(nums), 2) if nums else '',
                          (r.get('comments') or ''),
                          _ist_stamp(a.completed_at) if a.completed_at else '',
                          round((a.time_taken_ms or 0) / 1000.0, 1),
                          (item.extra_json or {}).get('audio', ''),
                          (item.text or '')]
                       + [(item.extra_json or {}).get(c, '') for c in SOURCE_META])

    buf = io.StringIO()
    csv.writer(buf).writerows(out)
    name = 'mdfs_scores%s.csv' % (('_' + language.lower()) if language else '')
    return csv_response(buf, name)
