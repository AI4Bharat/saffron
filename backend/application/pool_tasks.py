"""The ASR task layer: tasks, assignment, submissions and the annotator's tree."""

import csv
import io
from datetime import datetime, timedelta

from flask import current_app as app, jsonify, request, Response
from sqlalchemy import func

from application.models import (
    db, Rater, TeamMember, PoolItem, PoolTask, PoolTaskAssignment, PoolPull,
)
from application.views import token_required, _rater_in_scope, _serialize_team, ORG_NAME
from application.pool_api import _admin_pool_team
from application.pool_common import (
    DIFFICULTIES, FLAG_REASONS, ITEM_STATUSES, STALE_CLAIM_HOURS,
    _ist_day, _today_ist, _ist_stamp,
    _pool_team, _member, _current_rater, _serialize_item, _blank_counts, _with_progress,
    task_counts, task_category_counts, active_assignments, assigned_tasks_for,
    serialize_task, serialize_assignee, serialize_pull, pull_counts,
    release_pull_items, close_finished_pulls, release_stale_claims,
    my_work_by_task_type,
)

# How a task reads on the dashboard.
TASK_STATES = ['unassigned', 'not-started', 'in-progress', 'complete']


def _task_state(counts, has_assignee):
    if counts['total'] and counts['done'] >= counts['total']:
        return 'complete'
    if counts['claimed'] or counts['done']:
        return 'in-progress'
    return 'not-started' if has_assignee else 'unassigned'


def _sorted_tasks(tasks):
    """Language first, then class numerically where it looks like a number (so 'Class 10' never sorts between 'Class 1' and 'Class 2'), then the kind of work."""
    def key(t):
        klass = (t.class_label or '')
        return (t.language or '', len(klass), klass, getattr(t, 'task_type', '') or '')
    return sorted(tasks, key=key)


# Admin: the task list

@app.route('/api/pool/admin/tasks', methods=['GET'])
@token_required
def pool_admin_tasks(current_user):
    """Every task in the team's pool with its live progress and its holder."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    tasks = _sorted_tasks(PoolTask.query.filter_by(team_id=team.id, is_active=True).all())
    counts = task_counts(team.id)
    holders = active_assignments(team.id, [t.id for t in tasks])
    want_categories = request.args.get('categories') in ('1', 'true')
    categories = task_category_counts(team.id) if want_categories else {}

    args = request.args
    f_language = (args.get('language') or '').strip()
    f_class = (args.get('class') or '').strip()
    f_type = (args.get('task_type') or '').strip()
    f_state = (args.get('state') or '').strip()
    f_annotator = (args.get('annotator') or '').strip()
    search = (args.get('q') or '').strip().lower()

    rows, totals = [], _blank_counts(tasks=0, assigned=0, unassigned=0, complete=0,
                                     in_progress=0)
    languages, classes, task_types = set(), set(), set()
    for t in tasks:
        languages.add(t.language)
        if t.class_label:
            classes.add(str(t.class_label))
        task_types.add(getattr(t, 'task_type', None) or 'text-review')

        c = counts.get(t.id) or _with_progress(_blank_counts())
        assignment, holder = holders.get(t.id, (None, None))
        assignee = serialize_assignee(assignment, holder)
        state = _task_state(c, assignee is not None)

        # team-wide totals are computed before filtering, so the header numbers describe the pool rather than the current view
        totals['tasks'] += 1
        for k in ITEM_STATUSES + ['total']:
            totals[k] += c[k]
        totals['assigned' if assignee else 'unassigned'] += 1
        if state == 'complete':
            totals['complete'] += 1
        elif state == 'in-progress':
            totals['in_progress'] += 1

        if f_language and t.language != f_language:
            continue
        if f_class and str(t.class_label or '') != f_class:
            continue
        if f_type and (getattr(t, 'task_type', None) or 'text-review') != f_type:
            continue
        if f_state and state != f_state:
            continue
        if f_annotator:
            if f_annotator == 'none':
                if assignee:
                    continue
            elif not assignee or str(assignee['rater_id']) != f_annotator:
                continue
        if search:
            hay = f"{t.id} {t.language} {t.class_label or ''} " \
                  f"{assignee['name'] if assignee else ''}".lower()
            if search not in hay:
                continue

        row = serialize_task(t, c, assignee,
                             sorted(categories.get(t.id, {}).values(),
                                    key=lambda x: x['category']) if want_categories else None)
        row['state'] = state
        rows.append(row)

    _with_progress(totals)
    return jsonify({
        'team': _serialize_team(team),
        'tasks': rows,
        'totals': totals,
        'languages': sorted(languages),
        'classes': sorted(classes, key=lambda c: (len(c), c)),
        'task_types': sorted(task_types),
        'states': TASK_STATES,
        'shown': len(rows),
    }), 200


@app.route('/api/pool/admin/task/<int:task_id>', methods=['GET'])
@token_required
def pool_admin_task(current_user, task_id):
    """One task in full: progress by category, who holds it, every pull made against it, who has submitted what, and the latest submissions."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    task = PoolTask.query.filter_by(id=task_id, team_id=team.id).first()
    if task is None:
        return jsonify({'message': 'Task not found'}), 404

    counts = task_counts(team.id, [task.id]).get(task.id) or _with_progress(_blank_counts())
    cats = sorted(task_category_counts(team.id, [task.id]).get(task.id, {}).values(),
                  key=lambda c: c['category'])
    assignment, holder = active_assignments(team.id, [task.id]).get(task.id, (None, None))

    # everyone who has ever held or worked this task
    people = {}
    for rid, status, cnt in db.session.query(
        PoolItem.completed_by, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.task_id == task.id,
             PoolItem.completed_by.isnot(None)).group_by(
                 PoolItem.completed_by, PoolItem.status).all():
        slot = people.setdefault(rid, _blank_counts(rater_id=rid))
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt
    for rid, cnt in db.session.query(PoolItem.claimed_by, func.count(PoolItem.id)).filter(
            PoolItem.task_id == task.id, PoolItem.status == 'claimed').group_by(
                PoolItem.claimed_by).all():
        if rid:
            slot = people.setdefault(rid, _blank_counts(rater_id=rid))
            slot['claimed'] = cnt
            slot['total'] += cnt
    names = {r.id: r for r in Rater.query.filter(Rater.id.in_(list(people.keys()))).all()} \
        if people else {}
    annotators = []
    for rid, c in people.items():
        r = names.get(rid)
        annotators.append(dict(_with_progress(c),
                               name=r.name if r else f'Annotator #{rid}',
                               email=r.email if r else ''))
    annotators.sort(key=lambda a: -a['done'])

    pulls = PoolPull.query.filter_by(task_id=task.id).order_by(PoolPull.id.desc()).limit(100).all()
    pull_stats = pull_counts([p.pull_id for p in pulls])
    pull_names = {r.id: r.name for r in Rater.query.filter(
        Rater.id.in_([p.rater_id for p in pulls])).all()} if pulls else {}
    pull_rows = [dict(serialize_pull(p, pull_stats.get(p.pull_id), task),
                      annotator=pull_names.get(p.rater_id, f'Annotator #{p.rater_id}'))
                 for p in pulls]

    history = [dict(serialize_assignee(a, names.get(a.rater_id) or Rater.query.get(a.rater_id)),
                    is_active=bool(a.is_active),
                    revoked_at_ist=_ist_stamp(a.revoked_at))
               for a in PoolTaskAssignment.query.filter_by(task_id=task.id)
               .order_by(PoolTaskAssignment.assigned_at.desc()).limit(50).all()]

    recent_items = PoolItem.query.filter(
        PoolItem.task_id == task.id, PoolItem.completed_at.isnot(None)
    ).order_by(PoolItem.completed_at.desc()).limit(25).all()
    recent_ids = {i.completed_by for i in recent_items if i.completed_by}
    recent_names = {r.id: r.name for r in Rater.query.filter(
        Rater.id.in_(list(recent_ids))).all()} if recent_ids else {}
    recent = [dict(_serialize_item(it), annotator=recent_names.get(it.completed_by, ''))
              for it in recent_items]

    return jsonify({
        'task': dict(serialize_task(task, counts, serialize_assignee(assignment, holder), cats),
                     state=_task_state(counts, assignment is not None)),
        'annotators': annotators,
        'pulls': pull_rows,
        'assignment_history': history,
        'recent_submissions': recent,
    }), 200


# Admin: assignment (one task, one annotator)

@app.route('/api/pool/admin/tasks/assign', methods=['POST'])
@token_required
def pool_admin_tasks_assign(current_user):
    """Hand one or more whole tasks to ONE annotator."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}

    rater = Rater.query.get(data.get('rater_id')) if data.get('rater_id') else None
    if rater is None:
        return jsonify({'message': 'Annotator not found'}), 404
    if not _rater_in_scope(current_user, rater):
        return jsonify({'message': 'This annotator is not in your team.'}), 403
    member = TeamMember.query.filter_by(team_id=team.id, rater_id=rater.id,
                                        is_active=True).first()
    if member is None:
        return jsonify({'message': f'{rater.name} is not an active member of {team.name}. '
                                   'Add them to the team first.'}), 400

    ids = data.get('task_ids') or ([data['task_id']] if data.get('task_id') else [])
    try:
        ids = [int(i) for i in ids]
    except (TypeError, ValueError):
        return jsonify({'message': 'Task ids must be numbers.'}), 400
    if not ids:
        return jsonify({'message': 'Pick at least one task to assign.'}), 400

    tasks = {t.id: t for t in PoolTask.query.filter(
        PoolTask.id.in_(ids), PoolTask.team_id == team.id).all()}
    missing = [i for i in ids if i not in tasks]
    if missing:
        return jsonify({'message': f"Task(s) {', '.join(map(str, missing))} are not in "
                                   f"{team.name}."}), 404

    reassign = bool(data.get('reassign'))
    holders = active_assignments(team.id, ids)
    blocked = []
    for tid in ids:
        assignment, holder = holders.get(tid, (None, None))
        if assignment and assignment.rater_id != rater.id and not reassign:
            blocked.append(f"#{tid} ({holder.name if holder else 'someone else'})")
    if blocked:
        return jsonify({
            'message': 'One task can only ever belong to one annotator. Already taken: '
                       + ', '.join(blocked) + '.',
            'blocked': blocked,
        }), 409

    assigned, moved = [], []
    now = datetime.utcnow()
    try:
        for tid in ids:
            assignment, holder = holders.get(tid, (None, None))
            if assignment and assignment.rater_id == rater.id:
                continue                                  # already theirs
            if assignment:
                assignment.is_active = False
                assignment.revoked_at = now
                moved.append(f"#{tid} from {holder.name if holder else 'previous holder'}")
            # An earlier, revoked row for the same pair is reactivated rather than duplicated -- the (task, rater) pair is unique.
            previous = PoolTaskAssignment.query.filter_by(task_id=tid, rater_id=rater.id).first()
            if previous is not None:
                previous.is_active = True
                previous.revoked_at = None
                previous.assigned_at = now
                previous.assigned_by = current_user
            else:
                db.session.add(PoolTaskAssignment(task_id=tid, rater_id=rater.id,
                                                  assigned_by=current_user, assigned_at=now))
            assigned.append(tid)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_admin_tasks_assign failed: {e}")
        return jsonify({'message': 'Could not save that assignment. Please try again.'}), 500

    if not assigned:
        return jsonify({'message': f'{rater.name} already holds those task(s).',
                        'assigned': []}), 200
    msg = f"{len(assigned)} task(s) assigned to {rater.name}."
    if moved:
        msg += ' Taken over: ' + ', '.join(moved) + '.'
    return jsonify({'message': msg, 'assigned': assigned}), 200


@app.route('/api/pool/admin/tasks/unassign', methods=['POST'])
@token_required
def pool_admin_tasks_unassign(current_user):
    """Take tasks back."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}

    ids = data.get('task_ids') or ([data['task_id']] if data.get('task_id') else [])
    try:
        ids = [int(i) for i in ids] if ids else None
    except (TypeError, ValueError):
        return jsonify({'message': 'Task ids must be numbers.'}), 400
    rater_id = data.get('rater_id')
    if ids is None and not rater_id:
        return jsonify({'message': 'Say which task(s), or which annotator, to unassign.'}), 400

    holders = active_assignments(team.id, ids)
    targets = [(tid, a) for tid, (a, _) in holders.items()
               if rater_id is None or a.rater_id == int(rater_id)]
    if not targets:
        return jsonify({'message': 'Nothing to unassign.', 'unassigned': 0}), 200

    freed = 0
    if data.get('return_claimed'):
        touched = set()
        for tid, a in targets:
            for it in PoolItem.query.filter_by(task_id=tid, claimed_by=a.rater_id,
                                               status='claimed').all():
                it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
                touched.add(a.rater_id)
                freed += 1
        for rid in touched:
            close_finished_pulls(rid)

    n = 0
    now = datetime.utcnow()
    for _tid, a in targets:
        a.is_active = False
        a.revoked_at = now
        n += 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_admin_tasks_unassign failed: {e}")
        return jsonify({'message': 'Could not unassign that. Please try again.'}), 500

    msg = f'{n} task(s) unassigned.'
    if freed:
        msg += f' {freed} unfinished prompt(s) returned to the pool.'
    return jsonify({'message': msg, 'unassigned': n, 'released': freed}), 200


@app.route('/api/pool/admin/tasks/assignable', methods=['GET'])
@token_required
def pool_admin_tasks_assignable(current_user):
    """What the assign dialog needs: the team's annotators and every task with its holder, so the admin sees what is free before choosing."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    members = TeamMember.query.filter_by(team_id=team.id, is_active=True).all()
    raters = {r.id: r for r in Rater.query.filter(
        Rater.id.in_([m.rater_id for m in members])).all()} if members else {}
    holders = active_assignments(team.id)
    counts = task_counts(team.id)

    held_by = {}
    for tid, (a, _r) in holders.items():
        held_by[a.rater_id] = held_by.get(a.rater_id, 0) + 1

    annotators = []
    for m in members:
        r = raters.get(m.rater_id)
        if r is None or not getattr(r, 'is_active', True):
            continue
        annotators.append({
            'rater_id': m.rater_id, 'name': r.name, 'email': r.email,
            'pull_size': m.pull_size, 'tasks_held': held_by.get(m.rater_id, 0),
        })
    annotators.sort(key=lambda a: a['name'].lower())

    tasks = []
    for t in _sorted_tasks(PoolTask.query.filter_by(team_id=team.id, is_active=True).all()):
        c = counts.get(t.id) or _with_progress(_blank_counts())
        assignment, holder = holders.get(t.id, (None, None))
        tasks.append(serialize_task(t, c, serialize_assignee(assignment, holder)))

    return jsonify({'annotators': annotators, 'tasks': tasks}), 200


# Admin: submissions

def _submission_query(team, args):
    """The filtered set of prompts behind the submissions screen and its export."""
    q = PoolItem.query.filter(PoolItem.team_id == team.id)
    if args.get('task_id', type=int):
        q = q.filter(PoolItem.task_id == args.get('task_id', type=int))
    if args.get('language'):
        q = q.filter(PoolItem.language == args['language'])
    if args.get('class'):
        q = q.filter(PoolItem.class_label == args['class'])
    if args.get('category'):
        q = q.filter(PoolItem.category == args['category'])
    if args.get('difficulty'):
        q = q.filter(PoolItem.final_difficulty == args['difficulty'])
    if args.get('annotator', type=int):
        q = q.filter(PoolItem.completed_by == args.get('annotator', type=int))

    # 'submitted' is the default view: only prompts that actually have an answer.
    state = (args.get('state') or 'submitted').lower()
    if state == 'submitted':
        q = q.filter(PoolItem.status.in_(['completed', 'flagged']))
    elif state in ITEM_STATUSES:
        q = q.filter(PoolItem.status == state)
    elif state == 'pending':
        q = q.filter(PoolItem.status.in_(['available', 'claimed']))

    if args.get('edited') in ('1', 'true'):
        q = q.filter(PoolItem.is_edited == True)             # noqa: E712
    if args.get('flagged') in ('1', 'true'):
        q = q.filter(PoolItem.is_flagged == True)            # noqa: E712
    if args.get('changed') in ('1', 'true'):
        q = q.filter(PoolItem.final_difficulty.isnot(None),
                     PoolItem.source_difficulty.isnot(None),
                     PoolItem.final_difficulty != PoolItem.source_difficulty)

    # Dates are IST days; storage is UTC, so the window is shifted by 5h30.
    def _day(key):
        raw = (args.get(key) or '').strip()
        if not raw:
            return None
        try:
            return datetime.strptime(raw, '%Y-%m-%d') - timedelta(hours=5, minutes=30)
        except ValueError:
            return None
    frm, to = _day('from'), _day('to')
    if frm:
        q = q.filter(PoolItem.completed_at >= frm)
    if to:
        q = q.filter(PoolItem.completed_at < to + timedelta(days=1))

    search = (args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        clauses = [PoolItem.text.like(like), PoolItem.final_text.like(like)]
        if search.isdigit():
            clauses.append(PoolItem.id == int(search))
        q = q.filter(db.or_(*clauses))
    return q


@app.route('/api/pool/admin/submissions', methods=['GET'])
@token_required
def pool_admin_submissions(current_user):
    """Every submission, filterable and paginated."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    q = _submission_query(team, request.args)
    total = q.count()
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(max(1, request.args.get('per_page', 50, type=int)), 200)

    # SQLite sorts NULLs first ascending and last descending, which is exactly what these views want: unsubmitted prompts never push submissions off the first page.
    order = (request.args.get('sort') or 'recent').lower()
    if order == 'oldest':
        q = q.order_by(PoolItem.completed_at.asc(), PoolItem.id.asc())
    elif order == 'item':
        q = q.order_by(PoolItem.id.asc())
    else:
        q = q.order_by(PoolItem.completed_at.desc(), PoolItem.id.desc())

    items = q.offset((page - 1) * per_page).limit(per_page).all()
    ids = {i.completed_by for i in items if i.completed_by}
    names = {r.id: r.name for r in Rater.query.filter(Rater.id.in_(ids)).all()} if ids else {}
    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}

    rows = []
    for it in items:
        d = _serialize_item(it)
        d['annotator'] = names.get(it.completed_by)
        d['task_label'] = tasks[it.task_id].label if it.task_id in tasks else None
        d['difficulty_changed'] = bool(
            it.final_difficulty and it.source_difficulty
            and it.final_difficulty != it.source_difficulty)
        rows.append(d)

    return jsonify({
        'items': rows,
        'total': total,
        'page': page,
        'per_page': per_page,
        'pages': (total + per_page - 1) // per_page,
        'difficulties': DIFFICULTIES,
    }), 200


@app.route('/api/pool/admin/submissions/filters', methods=['GET'])
@token_required
def pool_admin_submission_filters(current_user):
    """The vocabulary of the submissions filter bar, read from the data itself so a newly loaded language or category appears without a code change."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    tasks = _sorted_tasks(PoolTask.query.filter_by(team_id=team.id, is_active=True).all())
    categories = [c or 'other' for (c,) in db.session.query(PoolItem.category).filter(
        PoolItem.team_id == team.id).distinct().order_by(PoolItem.category).all()]
    annotator_ids = [rid for (rid,) in db.session.query(PoolItem.completed_by).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by.isnot(None)).distinct().all()]
    annotators = [{'rater_id': r.id, 'name': r.name}
                  for r in Rater.query.filter(Rater.id.in_(annotator_ids))
                  .order_by(Rater.name).all()] if annotator_ids else []

    return jsonify({
        'tasks': [{'task_id': t.id, 'label': t.label, 'language': t.language,
                   'class': t.class_label} for t in tasks],
        'languages': sorted({t.language for t in tasks}),
        'classes': sorted({str(t.class_label) for t in tasks if t.class_label},
                          key=lambda c: (len(c), c)),
        'categories': categories,
        'annotators': annotators,
        'difficulties': DIFFICULTIES,
        'flag_reasons': FLAG_REASONS,
    }), 200


@app.route('/api/pool/admin/export_submissions_csv', methods=['GET'])
@token_required
def pool_export_submissions_csv(current_user):
    """Exactly what the submissions screen is showing, as a CSV."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    q = _submission_query(team, request.args)
    names = {r.id: (r.name, r.email or '') for r in Rater.query.all()}
    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Sr. No.', 'Task ID', 'Language', 'Class', 'Category', 'Prompt ID',
                'Original text', 'Submitted text', 'Edited',
                'Difficulty (generated)', 'Difficulty (annotator)', 'Difficulty changed',
                'Status', 'Flag reason', 'Notes', 'Annotator', 'Email',
                'Claimed (IST)', 'Submitted (IST)', 'Seconds', 'Revisions'])
    n = 0
    for it in q.order_by(PoolItem.id).yield_per(1000):
        n += 1
        name, email = names.get(it.completed_by, ('', ''))
        task = tasks.get(it.task_id)
        w.writerow([
            n, it.task_id or '', task.language if task else it.language,
            task.class_label if task else it.class_label, it.category, it.id,
            it.text, it.final_text or '', 'yes' if it.is_edited else 'no',
            it.source_difficulty or '', it.final_difficulty or '',
            'yes' if (it.final_difficulty and it.source_difficulty
                      and it.final_difficulty != it.source_difficulty) else 'no',
            it.status, it.flag_reason or '', (it.notes or '').replace('\n', ' '),
            name, email, _ist_stamp(it.claimed_at), _ist_stamp(it.completed_at),
            round((it.time_taken_ms or 0) / 1000.0, 1), it.revision or 0,
        ])

    stamp = datetime.utcnow().strftime('%Y%m%d')
    return Response(
        buf.getvalue(), mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename=asr_submissions_{stamp}.csv'})


# Annotator: my tasks, my pulls, my tree

@app.route('/api/pool/my/workspace', methods=['GET'])
@token_required
def pool_my_workspace(current_user):
    """Everything the pool workspace draws, in one call: the tasks this annotator holds with what is still free in each granularity, the pulls they are working on, and."""
    release_stale_claims()   # anything anyone abandoned over STALE_CLAIM_HOURS ago comes back
    team = _pool_team()
    if team is None:
        return jsonify({'message': 'Pool team not found'}), 404
    rater = _current_rater(current_user)
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404
    member = _member(rater, team)
    if member is None:
        return jsonify({'message': 'You are not a member of this team.'}), 403

    pairs = assigned_tasks_for(rater.id, team.id)
    task_ids = [t.id for t, _ in pairs]

    # --- what is still free in each of my tasks, per category and difficulty ---
    free_cat, free_diff = {}, {}
    if task_ids:
        for tid, cat, cnt in db.session.query(
            PoolItem.task_id, PoolItem.category, func.count(PoolItem.id)
        ).filter(PoolItem.task_id.in_(task_ids), PoolItem.status == 'available'
                 ).group_by(PoolItem.task_id, PoolItem.category).all():
            free_cat.setdefault(tid, {})[cat or 'other'] = cnt
        for tid, cat, diff, cnt in db.session.query(
            PoolItem.task_id, PoolItem.category, PoolItem.source_difficulty,
            func.count(PoolItem.id)
        ).filter(PoolItem.task_id.in_(task_ids), PoolItem.status == 'available'
                 ).group_by(PoolItem.task_id, PoolItem.category,
                            PoolItem.source_difficulty).all():
            free_diff.setdefault(tid, {}).setdefault(cat or 'other', {})[diff or 'Unset'] = cnt

    # --- my own numbers inside each task ---
    mine = {}
    if task_ids:
        for tid, status, cnt in db.session.query(
            PoolItem.task_id, PoolItem.status, func.count(PoolItem.id)
        ).filter(PoolItem.task_id.in_(task_ids),
                 db.or_(PoolItem.claimed_by == rater.id,
                        PoolItem.completed_by == rater.id)
                 ).group_by(PoolItem.task_id, PoolItem.status).all():
            slot = mine.setdefault(tid, _blank_counts())
            slot['total'] += cnt
            if status in slot:
                slot[status] += cnt

    overall = task_counts(team.id, task_ids)

    tasks = []
    for task, assignment in pairs:
        cats = free_cat.get(task.id, {})
        tasks.append({
            **serialize_task(task, overall.get(task.id) or _blank_counts()),
            'assigned_at_ist': _ist_stamp(assignment.assigned_at),
            'assigned_by': assignment.assigned_by,
            'available_total': sum(cats.values()),
            'available_by_category': [
                {'category': c, 'available': n,
                 'by_difficulty': sorted(
                     ({'difficulty': d, 'available': k}
                      for d, k in free_diff.get(task.id, {}).get(c, {}).items()),
                     key=lambda x: x['difficulty'])}
                for c, n in sorted(cats.items())],
            'mine': _with_progress(mine.get(task.id) or _blank_counts()),
        })

    # --- the pulls I am working on ---
    open_pulls = PoolPull.query.filter_by(rater_id=rater.id, team_id=team.id,
                                          status='open').order_by(PoolPull.id.desc()).all()
    stats = pull_counts([p.pull_id for p in open_pulls])
    task_by_id = {t.id: t for t, _ in pairs}
    pulls = [serialize_pull(p, stats.get(p.pull_id), task_by_id.get(p.task_id))
             for p in open_pulls]

    outstanding = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.claimed_by == rater.id,
        PoolItem.status == 'claimed').scalar() or 0
    today = 0
    since = datetime.utcnow() - timedelta(days=2)
    for (ts,) in db.session.query(PoolItem.completed_at).filter(
            PoolItem.completed_by == rater.id, PoolItem.completed_at >= since).all():
        if _ist_day(ts) == _today_ist():
            today += 1
    done_total = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater.id,
        PoolItem.status.in_(['completed', 'flagged'])).scalar() or 0

    # What they have done, per kind of work -- the numbers payment is based on, so the annotator sees exactly what the admin sees.
    by_task_type = my_work_by_task_type(team.id, rater.id)

    return jsonify({
        'team': _serialize_team(team),
        'organization': ORG_NAME,
        'annotator': {'id': rater.id, 'name': rater.name},
        'tasks': tasks,
        'pulls': pulls,
        'stats': {
            'assigned_tasks': len(tasks),
            'outstanding': outstanding,
            'completed_today': today,
            'completed_total': done_total,
            'available_total': sum(t['available_total'] for t in tasks),
            'pull_size': member.pull_size,
            'room': max(0, member.pull_size - outstanding),
            'by_task_type': by_task_type,
        },
        'stale_claim_hours': STALE_CLAIM_HOURS,
        'difficulties': DIFFICULTIES,
        'flag_reasons': FLAG_REASONS,
    }), 200


@app.route('/api/pool/my/tree', methods=['GET'])
@token_required
def pool_my_tree(current_user):
    """What this annotator has done, at every granularity: language -> class (task) -> category -> difficulty."""
    team = _pool_team()
    rater = _current_rater(current_user)
    if not (team and rater):
        return jsonify({'languages': [], 'totals': _with_progress(_blank_counts())}), 200

    rows = db.session.query(
        PoolItem.task_id, PoolItem.language, PoolItem.class_label, PoolItem.category,
        PoolItem.final_difficulty, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             db.or_(PoolItem.claimed_by == rater.id, PoolItem.completed_by == rater.id)
             ).group_by(PoolItem.task_id, PoolItem.language, PoolItem.class_label,
                        PoolItem.category, PoolItem.final_difficulty, PoolItem.status).all()

    languages, totals = {}, _blank_counts()
    for task_id, lang, klass, cat, diff, status, cnt in rows:
        lang = lang or 'Unknown'
        klass = str(klass) if klass not in (None, '') else '-'
        cat = cat or 'other'

        L = languages.setdefault(lang, _blank_counts(language=lang, classes={}))
        K = L['classes'].setdefault(klass, _blank_counts(**{'class': klass, 'task_id': task_id,
                                                            'categories': {}}))
        C = K['categories'].setdefault(cat, _blank_counts(category=cat, difficulties={}))
        for bucket in (totals, L, K, C):
            bucket['total'] += cnt
            if status in bucket:
                bucket[status] += cnt
        if status == 'completed' and diff:
            C['difficulties'][diff] = C['difficulties'].get(diff, 0) + cnt

    out = []
    for lang in sorted(languages):
        L = languages[lang]
        classes = []
        for klass in sorted(L['classes'], key=lambda c: (len(c), c)):
            K = L['classes'][klass]
            K['categories'] = [_with_progress(K['categories'][c])
                               for c in sorted(K['categories'])]
            classes.append(_with_progress(K))
        L['classes'] = classes
        out.append(_with_progress(L))

    return jsonify({'languages': out, 'totals': _with_progress(totals)}), 200


@app.route('/api/pool/my/submissions', methods=['GET'])
@token_required
def pool_my_submissions(current_user):
    """The work this annotator has done, prompt by prompt."""
    team = _pool_team()
    rater = _current_rater(current_user)
    if not (team and rater):
        return jsonify({'items': [], 'total': 0, 'page': 1, 'pages': 1}), 200

    args = request.args
    q = PoolItem.query.filter(PoolItem.team_id == team.id,
                              PoolItem.completed_by == rater.id)
    if args.get('task_id', type=int):
        q = q.filter(PoolItem.task_id == args.get('task_id', type=int))
    if args.get('category'):
        q = q.filter(PoolItem.category == args['category'])
    if args.get('difficulty'):
        q = q.filter(PoolItem.final_difficulty == args['difficulty'])
    state = (args.get('state') or 'submitted').lower()
    if state == 'submitted':
        q = q.filter(PoolItem.status.in_(['completed', 'flagged']))
    elif state in ITEM_STATUSES:
        q = q.filter(PoolItem.status == state)
    if args.get('edited') in ('1', 'true'):
        q = q.filter(PoolItem.is_edited == True)             # noqa: E712
    search = (args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        clauses = [PoolItem.text.like(like), PoolItem.final_text.like(like)]
        if search.isdigit():
            clauses.append(PoolItem.id == int(search))
        q = q.filter(db.or_(*clauses))

    total = q.count()
    page = max(1, args.get('page', 1, type=int))
    per_page = min(max(1, args.get('per_page', 25, type=int)), 200)
    items = (q.order_by(PoolItem.completed_at.desc(), PoolItem.id.desc())
             .offset((page - 1) * per_page).limit(per_page).all())

    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    rows = []
    for it in items:
        d = _serialize_item(it)
        d['task_label'] = tasks[it.task_id].label if it.task_id in tasks else None
        d['difficulty_changed'] = bool(
            it.final_difficulty and it.source_difficulty
            and it.final_difficulty != it.source_difficulty)
        rows.append(d)

    return jsonify({'items': rows, 'total': total, 'page': page, 'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page}), 200


@app.route('/api/pool/my/export_submissions_csv', methods=['GET'])
@token_required
def pool_my_export_submissions(current_user):
    """The annotator's own work as a CSV: the original prompt, what they submitted, the label they gave it and when."""
    team = _pool_team()
    rater = _current_rater(current_user)
    if not (team and rater):
        return jsonify({'message': 'Not found'}), 404

    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Sr. No.', 'Task ID', 'Task', 'Language', 'Class', 'Category', 'Prompt ID',
                'Original text', 'My submission', 'Edited',
                'Difficulty (suggested)', 'Difficulty (mine)', 'Status', 'Flag reason',
                'Notes', 'Submitted (IST)', 'Seconds'])
    n = 0
    for it in PoolItem.query.filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater.id,
        PoolItem.status.in_(['completed', 'flagged'])
    ).order_by(PoolItem.completed_at.desc()).yield_per(500):
        n += 1
        t = tasks.get(it.task_id)
        w.writerow([n, it.task_id or '', t.label if t else '', it.language, it.class_label,
                    it.category, it.id, it.text, it.final_text or '',
                    'yes' if it.is_edited else 'no',
                    it.source_difficulty or '', it.final_difficulty or '', it.status,
                    it.flag_reason or '', (it.notes or '').replace('\n', ' '),
                    _ist_stamp(it.completed_at),
                    round((it.time_taken_ms or 0) / 1000.0, 1)])

    stamp = datetime.utcnow().strftime('%Y%m%d')
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':
                             f'attachment; filename=my_asr_work_{stamp}.csv'})


@app.route('/api/pool/my/pull/<pull_id>', methods=['DELETE'])
@token_required
def pool_my_pull_delete(current_user, pull_id):
    """RETIRED: annotators no longer hand pulls back themselves. Anything they do not finish returns to the pool automatically after STALE_CLAIM_HOURS."""
    return jsonify({'message': 'Pulls can no longer be returned by hand. Anything you do not '
                               'finish goes back to the pool automatically after '
                               f'{STALE_CLAIM_HOURS} hours.'}), 410
