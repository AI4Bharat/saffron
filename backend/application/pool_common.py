"""Shared vocabulary and helpers for the pool workflow (the ASR team)."""

import os
from datetime import datetime, timedelta

from flask import request, Response
from sqlalchemy import func

from application.models import (
    db, Rater, Team, TeamMember, PoolItem, PoolTask, PoolTaskAssignment, PoolPull,
)
from application.views import _team_by_key

# Difficulty vocabulary the UI offers and the API accepts.
DIFFICULTIES = ['Easy', 'Medium', 'Hard']

# Why an annotator may hand a prompt back instead of labelling it.
FLAG_REASONS = [
    'Not in the target language',
    'Gibberish / not readable',
    'Offensive or unsafe content',
    'Duplicate of another item',
    'Too long to read aloud',
    'Encoding / rendering broken',
    'Other',
]

# Claimed-but-unfinished items return to the pool automatically after this long (annotators cannot hand pulls back by hand -- this sweep is the only way out).
STALE_CLAIM_HOURS = int(os.environ.get('POOL_STALE_CLAIM_HOURS', '24'))

# The sweep runs lazily on pool traffic, at most once per worker per this many seconds.
_STALE_SWEEP_INTERVAL_S = int(os.environ.get('POOL_STALE_SWEEP_INTERVAL_S', '300'))
_last_stale_sweep = [0.0]

# The task type items fall back to when the source data does not name one.
DEFAULT_TASK_TYPE = os.environ.get('POOL_DEFAULT_TASK_TYPE', 'text-review')

# Human labels for the kinds of work a pool can hold. Extendable through the environment (POOL_TASK_TYPE_LABELS='{"key": "Label", ...}') without a code change; unknown keys fall back to a humanised form of the key itself.
TASK_TYPE_LABELS = {
    'text-review': 'Text review (edit + difficulty)',
}
try:
    import json as _json
    TASK_TYPE_LABELS.update(_json.loads(os.environ.get('POOL_TASK_TYPE_LABELS', '{}')))
except (ValueError, TypeError):
    pass

# The fixed batch sizes a "Get prompts" press offers. There is no ceiling on how many batches an annotator may take; extendable through the environment without a code change.
try:
    BATCH_SIZES = [int(x) for x in
                   os.environ.get('POOL_BATCH_SIZES', '20,30,50').split(',') if x.strip()]
except ValueError:
    BATCH_SIZES = []
if not BATCH_SIZES:
    BATCH_SIZES = [20, 30, 50]

# The states a pool item can be in, in the order the dashboards read them.
ITEM_STATUSES = ['available', 'claimed', 'completed', 'flagged']

_IST = timedelta(hours=5, minutes=30)


def task_type_label(key):
    key = key or DEFAULT_TASK_TYPE
    return TASK_TYPE_LABELS.get(key) or key.replace('-', ' ').replace('_', ' ').capitalize()


# time (every annotator and admin on this project reads IST; storage is UTC)

def _ist_day(dt):
    return (dt + _IST).date().isoformat() if dt else None


def _today_ist():
    return _ist_day(datetime.utcnow())


def _ist_stamp(dt):
    """'YYYY-MM-DD HH:MM:SS' in IST, or ''."""
    return (dt + _IST).strftime('%Y-%m-%d %H:%M:%S') if dt else ''


# team / member lookup

def _pool_team(default_key=None):
    """The pool team this request is about: ?team=<key> (or a 'team' body field) wins; otherwise the only active pool-workflow team. Nothing here assumes a particular team exists."""
    key = request.args.get('team') or (request.get_json(silent=True) or {}).get('team')
    team = _team_by_key(key) if key else None
    if team is None and default_key:
        team = _team_by_key(default_key)
    if team is None:
        pool_teams = Team.query.filter_by(workflow='pool', is_active=True).order_by(
            Team.id).all()
        team = pool_teams[0] if pool_teams else None
    return team


def _member(rater, team):
    if not rater or not team:
        return None
    return TeamMember.query.filter_by(team_id=team.id, rater_id=rater.id,
                                      is_active=True).first()


def _current_rater(current_user):
    return Rater.query.filter_by(name=current_user).first()


def team_setting(team, key, default=None):
    """One switch out of the team's settings bag (Team.settings JSON)."""
    s = getattr(team, 'settings', None) if team is not None else None
    return s.get(key, default) if isinstance(s, dict) else default


def difficulty_required_for(team, task, category):
    """Whether a prompt in this (language, class, category) slice must carry a difficulty label. Most specific wins: the category override on the task, then the task (= language + class) override, then the team default (on)."""
    s = getattr(task, 'settings', None) if task is not None else None
    if isinstance(s, dict):
        byc = s.get('difficulty_annotation_by_category')
        if isinstance(byc, dict) and category is not None and byc.get(category) is not None:
            return bool(byc[category])
        if s.get('difficulty_annotation') is not None:
            return bool(s['difficulty_annotation'])
    return bool(team_setting(team, 'difficulty_annotation', True))


def csv_response(buf, filename):
    """A CSV download that Excel opens with the right encoding: the BOM makes Excel read UTF-8, so Hindi/Tamil/Telugu/... text renders instead of mojibake."""
    return Response(
        '\ufeff' + buf.getvalue(), mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'})


def _allowed_languages(member, team):
    """Languages this annotator may be handed work in."""
    langs = [x.strip() for x in ((member.languages if member else '') or '').split(',') if x.strip()]
    if langs:
        return langs
    return [row[0] for row in db.session.query(PoolItem.language)
            .filter(PoolItem.team_id == team.id).distinct().order_by(PoolItem.language).all()]


# item serialisation

def _serialize_item(it, include_original=True):
    out = {
        'id': it.id,
        'task_id': it.task_id,
        'language': it.language,
        'class': it.class_label,
        'category': it.category,
        'source_difficulty': it.source_difficulty,
        'source': it.source,
        'n_words': it.n_words,
        'text': it.final_text if it.final_text is not None else it.text,
        'status': it.status,
        'final_difficulty': it.final_difficulty,
        'is_edited': bool(it.is_edited),
        'is_flagged': bool(it.is_flagged),
        'flag_reason': it.flag_reason,
        'notes': it.notes,
        'pull_id': it.pull_id,
        'task_type': it.task_type or DEFAULT_TASK_TYPE,
        'task_type_label': task_type_label(it.task_type),
        'claimed_at': it.claimed_at.isoformat() if it.claimed_at else None,
        'claimed_at_ist': _ist_stamp(it.claimed_at),
        'completed_at': it.completed_at.isoformat() if it.completed_at else None,
        'completed_at_ist': _ist_stamp(it.completed_at),
        'time_taken_ms': it.time_taken_ms,
        'revision': it.revision or 0,
    }
    if include_original:
        out['original_text'] = it.text
    return out


# the task layer

def _blank_counts(**extra):
    d = {'total': 0, 'available': 0, 'claimed': 0, 'completed': 0, 'flagged': 0}
    d.update(extra)
    return d


def _with_progress(counts):
    """Add the two derived numbers every table shows, so no caller computes them a slightly different way."""
    counts['done'] = counts['completed'] + counts['flagged']
    counts['progress'] = (round(100.0 * counts['done'] / counts['total'], 1)
                          if counts['total'] else 0.0)
    return counts


def task_counts(team_id, task_ids=None):
    """{task_id: counts} for a team, in one grouped scan."""
    q = db.session.query(PoolItem.task_id, PoolItem.status, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team_id, PoolItem.task_id.isnot(None))
    if task_ids is not None:
        if not task_ids:
            return {}
        q = q.filter(PoolItem.task_id.in_(list(task_ids)))
    out = {}
    for task_id, status, cnt in q.group_by(PoolItem.task_id, PoolItem.status).all():
        slot = out.setdefault(task_id, _blank_counts())
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt
    return {k: _with_progress(v) for k, v in out.items()}


def task_category_counts(team_id, task_ids=None):
    """{task_id: {category: counts}} -- the granularity an annotator pulls at."""
    q = db.session.query(PoolItem.task_id, PoolItem.category, PoolItem.status,
                         func.count(PoolItem.id)).filter(
        PoolItem.team_id == team_id, PoolItem.task_id.isnot(None))
    if task_ids is not None:
        if not task_ids:
            return {}
        q = q.filter(PoolItem.task_id.in_(list(task_ids)))
    out = {}
    for task_id, category, status, cnt in q.group_by(
            PoolItem.task_id, PoolItem.category, PoolItem.status).all():
        slot = out.setdefault(task_id, {}).setdefault(category or 'other', _blank_counts(
            category=category or 'other'))
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt
    return {t: {c: _with_progress(v) for c, v in cats.items()} for t, cats in out.items()}


def active_assignments(team_id, task_ids=None):
    """{task_id: [(assignment, rater), ...]} for the tasks that currently have a holder. A task held whole has one entry (category None, listed first); a task split by category has one entry per category."""
    q = (db.session.query(PoolTaskAssignment, Rater)
         .join(PoolTask, PoolTask.id == PoolTaskAssignment.task_id)
         .outerjoin(Rater, Rater.id == PoolTaskAssignment.rater_id)
         .filter(PoolTask.team_id == team_id,
                 PoolTaskAssignment.is_active == True))          # noqa: E712
    if task_ids is not None:
        if not task_ids:
            return {}
        q = q.filter(PoolTaskAssignment.task_id.in_(list(task_ids)))
    out = {}
    for a, r in q.all():
        out.setdefault(a.task_id, []).append((a, r))
    for rows in out.values():
        rows.sort(key=lambda ar: (ar[0].category is not None, ar[0].category or ''))
    return out


def primary_holder(holder_rows):
    """(assignment, rater) of the WHOLE-task holder, or (None, None). Category holders never count as 'the' assignee of a task."""
    for a, r in (holder_rows or []):
        if a.category is None:
            return a, r
    return None, None


def allowed_categories(assignments):
    """None when any assignment covers the whole task (no restriction); otherwise the set of categories these assignments grant."""
    cats = set()
    for a in assignments:
        if a.category is None:
            return None
        cats.add(a.category)
    return cats


def assigned_tasks_for(rater_id, team_id):
    """[(task, [assignments])] this annotator currently holds, oldest first. A task appears once even when they hold several of its categories."""
    rows = (db.session.query(PoolTask, PoolTaskAssignment)
            .join(PoolTaskAssignment, PoolTaskAssignment.task_id == PoolTask.id)
            .filter(PoolTaskAssignment.rater_id == rater_id,
                    PoolTaskAssignment.is_active == True,          # noqa: E712
                    PoolTask.team_id == team_id,
                    PoolTask.is_active == True)                    # noqa: E712
            .order_by(PoolTaskAssignment.assigned_at, PoolTask.id).all())
    out, index = [], {}
    for task, a in rows:
        if task.id not in index:
            index[task.id] = len(out)
            out.append((task, []))
        out[index[task.id]][1].append(a)
    return out


def assigned_task_ids(rater_id, team_id):
    return [t.id for t, _ in assigned_tasks_for(rater_id, team_id)]


def serialize_task(task, counts=None, assignee=None, categories=None):
    """One task row as every screen shows it: the id an admin quotes, what it covers, how far along it is and who holds it."""
    out = {
        'task_id': task.id,
        'language': task.language,
        'class': task.class_label,
        'label': task.label,
        'task_type': getattr(task, 'task_type', None) or DEFAULT_TASK_TYPE,
        'task_type_label': task_type_label(getattr(task, 'task_type', None)),
        'item_count': task.item_count,
        'is_active': bool(task.is_active),
        'created_at': task.created_at.isoformat() if task.created_at else None,
    }
    out.update(_with_progress(dict(counts or _blank_counts())))
    out['assignee'] = assignee
    out['categories'] = categories
    return out


def serialize_assignee(assignment, rater):
    if assignment is None:
        return None
    return {
        'rater_id': assignment.rater_id,
        'name': rater.name if rater else f'Annotator #{assignment.rater_id}',
        'email': rater.email if rater else '',
        'is_active': bool(getattr(rater, 'is_active', True)) if rater else False,
        'category': assignment.category,        # None = the whole task
        'assigned_by': assignment.assigned_by,
        'assigned_at': assignment.assigned_at.isoformat() if assignment.assigned_at else None,
        'assigned_at_ist': _ist_stamp(assignment.assigned_at),
    }


def _revoke_assignments(team_id, rater_id=None, task_ids=None):
    """Put tasks back on the shelf."""
    q = (PoolTaskAssignment.query
         .join(PoolTask, PoolTask.id == PoolTaskAssignment.task_id)
         .filter(PoolTask.team_id == team_id,
                 PoolTaskAssignment.is_active == True))            # noqa: E712
    if rater_id is not None:
        q = q.filter(PoolTaskAssignment.rater_id == rater_id)
    if task_ids is not None:
        if not task_ids:
            return 0
        q = q.filter(PoolTaskAssignment.task_id.in_(list(task_ids)))
    now = datetime.utcnow()
    n = 0
    for a in q.all():
        a.is_active = False
        a.revoked_at = now
        n += 1
    return n


def release_pull_items(pull, rater_id=None):
    """Hand a pull's UNFINISHED prompts back to the pool and close the pull."""
    q = PoolItem.query.filter(PoolItem.pull_id == pull.pull_id,
                              PoolItem.status == 'claimed')
    if rater_id is not None:
        q = q.filter(PoolItem.claimed_by == rater_id)
    freed = 0
    for it in q.all():
        it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
        freed += 1
    pull.status = 'released'
    pull.released_at = datetime.utcnow()
    return freed


def my_work_by_task_type(team_id, rater_id):
    """One row per kind of work this annotator has submitted: counts, edits, flags and total time. These are the payment-relevant numbers, shown identically to the annotator and the admin."""
    from sqlalchemy import case

    ttype = func.coalesce(PoolItem.task_type, 'text-review')
    rows = db.session.query(
        ttype,
        func.count(PoolItem.id),
        func.sum(case((PoolItem.status == 'completed', 1), else_=0)),
        func.sum(case((PoolItem.is_flagged == True, 1), else_=0)),      # noqa: E712
        func.sum(case((PoolItem.is_edited == True, 1), else_=0)),       # noqa: E712
        func.sum(func.coalesce(PoolItem.time_taken_ms, 0)),
    ).filter(
        PoolItem.team_id == team_id, PoolItem.completed_by == rater_id,
        PoolItem.status.in_(['completed', 'flagged']),
    ).group_by(ttype).all()

    out = []
    for key, total, completed, flagged, edited, ms in rows:
        seconds = round((ms or 0) / 1000.0)
        out.append({
            'task_type': key,
            'task_type_label': task_type_label(key),
            'submitted': int(total or 0),
            'completed': int(completed or 0),
            'flagged': int(flagged or 0),
            'edited': int(edited or 0),
            'seconds': seconds,
            'hours': round(seconds / 3600.0, 2),
        })
    out.sort(key=lambda r: -r['submitted'])
    return out


def release_stale_claims(team_id=None, force=False):
    """Hand every claimed-but-unfinished item older than STALE_CLAIM_HOURS back to the pool. Runs lazily on pool traffic (throttled per worker); submitted work is never touched. Returns how many items went back."""
    import time

    now = time.monotonic()
    if not force and now - _last_stale_sweep[0] < _STALE_SWEEP_INTERVAL_S:
        return 0
    _last_stale_sweep[0] = now

    cutoff = datetime.utcnow() - timedelta(hours=STALE_CLAIM_HOURS)
    q = PoolItem.query.filter(PoolItem.status == 'claimed', PoolItem.claimed_at < cutoff)
    if team_id is not None:
        q = q.filter(PoolItem.team_id == team_id)
    stale = q.all()
    if not stale:
        return 0

    touched_raters, touched_pulls = set(), set()
    for it in stale:
        if it.claimed_by:
            touched_raters.add(it.claimed_by)
        if it.pull_id:
            touched_pulls.add(it.pull_id)
        it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
    # Pulls that lost items to the sweep read 'released'; a rater's other pulls that are simply finished read 'done' (close_finished_pulls).
    if touched_pulls:
        now_dt = datetime.utcnow()
        for pull in PoolPull.query.filter(PoolPull.pull_id.in_(list(touched_pulls)),
                                          PoolPull.status == 'open').all():
            pull.status = 'released'
            pull.released_at = now_dt
    for rid in touched_raters:
        close_finished_pulls(rid)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return 0
    return len(stale)


def close_finished_pulls(rater_id):
    """Mark as 'done' every open pull of this annotator that has no claimed prompts left."""
    open_pulls = PoolPull.query.filter_by(rater_id=rater_id, status='open').all()
    if not open_pulls:
        return
    ids = [p.pull_id for p in open_pulls]
    still_open = {pid for (pid,) in db.session.query(PoolItem.pull_id).filter(
        PoolItem.pull_id.in_(ids), PoolItem.status == 'claimed').distinct().all()}
    for p in open_pulls:
        if p.pull_id not in still_open:
            p.status = 'done'


def serialize_pull(pull, counts=None, task=None):
    out = {
        'pull_id': pull.pull_id,
        'task_id': pull.task_id,
        'task_label': task.label if task else None,
        'language': task.language if task else None,
        'class': task.class_label if task else None,
        'category': pull.category or '',
        'source_difficulty': pull.source_difficulty or '',
        'requested': pull.requested,
        'item_count': pull.item_count,
        'status': pull.status,
        'origin': pull.origin,
        'created_at': pull.created_at.isoformat() if pull.created_at else None,
        'created_at_ist': _ist_stamp(pull.created_at),
        'released_at_ist': _ist_stamp(pull.released_at),
    }
    out.update(_with_progress(dict(counts or _blank_counts())))
    return out


def pull_counts(pull_ids):
    """{pull_id: counts} for a set of pulls, in one grouped scan."""
    if not pull_ids:
        return {}
    out = {}
    for pid, status, cnt in db.session.query(
        PoolItem.pull_id, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.pull_id.in_(list(pull_ids))).group_by(
            PoolItem.pull_id, PoolItem.status).all():
        slot = out.setdefault(pid, _blank_counts())
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt
    return {k: _with_progress(v) for k, v in out.items()}
