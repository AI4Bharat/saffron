"""Pool workflow API (the ASR team's way of working)."""

import csv
import io
import json
import os
import threading
import time
import uuid
from datetime import datetime, timedelta

from flask import current_app as app, jsonify, request, Response, send_file
from sqlalchemy import bindparam, func, text

from application.models import (
    db, Rater, Team, TeamMember, PoolAnnotation, PoolItem, PoolUpload, PoolTask,
    PoolTaskAssignment, PoolPull,
)
from application.views import (
    token_required, _is_admin, _admin_scope, _team_by_key, _request_team_id,
    _serialize_team, _rater_in_scope, ORG_NAME,
)
from application.pool_common import (  # noqa: F401  (re-exported for pool_tasks)
    BATCH_SIZES, DIFFICULTIES, FLAG_REASONS, STALE_CLAIM_HOURS, TASK_TYPE_LABELS, ITEM_STATUSES,
    task_type_label, _ist_day, _today_ist, _ist_stamp, _IST, _pool_team, _member,
    _current_rater, _allowed_languages, _serialize_item, _blank_counts,
    _with_progress, task_counts, task_category_counts, active_assignments,
    assigned_tasks_for, assigned_task_ids, primary_holder, allowed_categories,
    team_setting, open_items_cap, open_items_held, difficulty_required_for,
    valid_mdfs_results, MDFS_DIMENSIONS, annotations_target, refresh_item_state,
    csv_response, serialize_task, serialize_assignee,
    serialize_pull, pull_counts, release_pull_items, release_claims,
    close_finished_pulls,
    _revoke_assignments, release_stale_claims, my_work_by_task_type,
)


# Annotator endpoints

@app.route('/api/pool/summary', methods=['GET'])
@token_required
def pool_summary(current_user):
    """Everything the annotator's ASR home screen needs in one call."""
    team = _pool_team()
    if team is None:
        return jsonify({'message': 'Pool team not found'}), 404
    rater = _current_rater(current_user)
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404
    member = _member(rater, team)
    if member is None:
        return jsonify({'message': 'You are not a member of this team.'}), 403

    # Their own working set + lifetime numbers, per language.
    mine = db.session.query(
        PoolItem.language, PoolItem.status, func.count(PoolItem.id)
    ).filter(
        PoolItem.team_id == team.id,
        db.or_(PoolItem.claimed_by == rater.id, PoolItem.completed_by == rater.id),
    ).group_by(PoolItem.language, PoolItem.status).all()

    per_lang = {}
    for lang, status, cnt in mine:
        slot = per_lang.setdefault(lang, {'language': lang, 'claimed': 0,
                                          'completed': 0, 'flagged': 0})
        if status in slot:
            slot[status] += cnt

    outstanding = sum(s['claimed'] for s in per_lang.values())
    done_total = sum(s['completed'] + s['flagged'] for s in per_lang.values())

    # What is still free to pull, counted ONLY inside the tasks this annotator has been assigned -- the pool at large is none of their business.
    my_task_ids = assigned_task_ids(rater.id, team.id)
    available = {}
    if my_task_ids:
        for lang, cnt in db.session.query(
            PoolItem.language, func.count(PoolItem.id)
        ).filter(PoolItem.task_id.in_(my_task_ids),
                 PoolItem.status == 'available').group_by(PoolItem.language).all():
            available[lang] = cnt

    # Today's output (IST day boundary).
    since = datetime.utcnow() - timedelta(days=2)
    today = 0
    for (ts,) in db.session.query(PoolItem.completed_at).filter(
        PoolItem.completed_by == rater.id, PoolItem.completed_at >= since
    ).all():
        if _ist_day(ts) == _today_ist():
            today += 1

    return jsonify({
        'team': _serialize_team(team),
        'organization': ORG_NAME,
        'annotator': {'id': rater.id, 'name': rater.name},
        'languages': sorted(available.keys()),
        'assigned_tasks': len(my_task_ids),
        'available_by_language': available,
        'available_total': sum(available.values()),
        'my_by_language': sorted(per_lang.values(), key=lambda x: x['language']),
        'outstanding': outstanding,
        'completed_total': done_total,
        'completed_today': today,
        'batch_sizes': BATCH_SIZES,
        'max_open_items': open_items_cap(team),
        'can_pull': sum(available.values()) > 0 and
                    (not open_items_cap(team) or outstanding < open_items_cap(team)),
        'difficulty_annotation': bool(team_setting(team, 'difficulty_annotation', True)),
        'difficulties': DIFFICULTIES,
        'flag_reasons': FLAG_REASONS,
    }), 200


@app.route('/api/pool/pull', methods=['POST'])
@token_required
def pool_pull(current_user):
    """Hand this annotator a slice of one of THEIR tasks."""
    release_stale_claims()   # abandoned work returns to the pool before new work is handed out
    data = request.get_json(silent=True) or {}
    team = _pool_team()
    if team is None:
        return jsonify({'message': 'Pool team not found'}), 404
    rater = _current_rater(current_user)
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404
    member = _member(rater, team)
    if member is None:
        return jsonify({'message': 'You are not a member of this team.'}), 403

    # --- which task? It must be one of theirs. ---
    my_tasks = {t.id: (t, assignments) for t, assignments in
                assigned_tasks_for(rater.id, team.id)}
    if not my_tasks:
        return jsonify({'message': 'No tasks have been assigned to you yet. '
                                   'Your team admin assigns the tasks you may work on.',
                        'claimed': 0}), 403
    try:
        task_id = int(data.get('task_id') or 0)
    except (TypeError, ValueError):
        task_id = 0
    task, assignments = my_tasks.get(task_id, (None, None))
    if task is None:
        return jsonify({'message': 'Pick one of the tasks assigned to you.',
                        'claimed': 0}), 403
    # None = the whole task is theirs; otherwise only these categories.
    my_cats = allowed_categories(assignments)

    # --- how many? A fixed batch (20/30/50), bounded by the team's ceiling on claimed-but-unfinished prompts: whatever they still hold counts against it, so they must submit before they can pull more. ---
    cap = open_items_cap(team)
    held = open_items_held(team.id, rater.id) if cap else 0
    if cap and held >= cap:
        return jsonify({'message': f'You are holding {held} unfinished prompt(s) — the '
                                   f'limit is {cap} at a time. Submit those first, '
                                   'then you can pull more.',
                        'claimed': 0, 'outstanding': held, 'max_open_items': cap}), 403
    try:
        want = int(data.get('count') or BATCH_SIZES[0])
    except (TypeError, ValueError):
        want = BATCH_SIZES[0]
    want = max(1, min(want, 500))
    if cap:
        want = min(want, cap - held)

    # Plain equality filters inside the same single statement, so the no-overlap guarantee is untouched: whatever the filter, only one pull wins a row.
    category = (data.get('category') or '').strip().lower()
    difficulty = (data.get('difficulty') or '').strip().title()
    if category and my_cats is not None and category not in my_cats:
        return jsonify({'message': f"Only {', '.join(sorted(my_cats))} of this task "
                                   'is assigned to you.', 'claimed': 0}), 403
    extra_sql = ''
    params = {}
    expanding = []
    if category:
        extra_sql += ' AND category = :category'
        params['category'] = category
    elif my_cats is not None:
        # They asked for "any type" but only hold some categories: stay inside them.
        extra_sql += ' AND category IN :my_cats'
        params['my_cats'] = sorted(my_cats)
        expanding.append('my_cats')
    if difficulty:
        extra_sql += ' AND source_difficulty = :difficulty'
        params['difficulty'] = difficulty

    pull_id = uuid.uuid4().hex
    now = datetime.utcnow()
    # No two annotators may ever claim the same row. SQLite gets that from its single-writer serialization; PostgreSQL needs the selected rows locked (SKIP LOCKED so concurrent pulls take disjoint rows instead of waiting).
    row_lock = ('FOR UPDATE SKIP LOCKED'
                if db.engine.dialect.name == 'postgresql' else '')
    # How many annotators should answer each prompt (a project-level setting).
    # A prompt is offered while it has fewer than this many answers-or-holders, and
    # never twice to the same person, so N annotators means N DIFFERENT annotators.
    target = annotations_target(team, task)
    try:
        stmt = text(f"""
            INSERT INTO pool_annotation
                   (item_id, rater_id, team_id, task_id, pull_id, status, claimed_at)
            SELECT id, :rid, :team, :task, :pull, 'claimed', :now
              FROM (
                   SELECT i.id FROM pool_item i
                    WHERE i.task_id=:task
                          -- The annotation count is the only authority on whether a
                          -- prompt still needs work. Testing i.status too would freeze
                          -- out prompts already marked complete under a SMALLER target,
                          -- so raising N would never collect the extra answers.
                          AND (SELECT count(*) FROM pool_annotation a
                                WHERE a.item_id = i.id
                                  AND a.status IN ('claimed','completed','flagged'))
                              < :target
                          AND NOT EXISTS (SELECT 1 FROM pool_annotation mine
                                           WHERE mine.item_id = i.id
                                             AND mine.rater_id = :rid)
                          {extra_sql}
                    ORDER BY i.id
                    LIMIT :n {row_lock}) picked
        """)
        for name in expanding:
            stmt = stmt.bindparams(bindparam(name, expanding=True))
        res = db.session.execute(stmt, {'rid': rater.id, 'now': now, 'pull': pull_id,
                                        'task': task.id, 'n': want,
                                        'team': team.id, 'target': target, **params})
        claimed = res.rowcount or 0
        if claimed:
            # The items just taken now carry one more holder, so re-derive their state.
            for it in PoolItem.query.filter(PoolItem.id.in_(
                    db.session.query(PoolAnnotation.item_id).filter_by(pull_id=pull_id))).all():
                refresh_item_state(it, target)
        if claimed:
            db.session.add(PoolPull(
                pull_id=pull_id, team_id=team.id, task_id=task.id, rater_id=rater.id,
                category=category or None, source_difficulty=difficulty or None,
                requested=want, item_count=claimed, status='open', origin='self',
                created_at=now))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_pull failed: {e}")
        return jsonify({'message': 'Could not fetch work right now. Please try again.'}), 500

    items = PoolItem.query.filter(PoolItem.id.in_(
        db.session.query(PoolAnnotation.item_id).filter_by(pull_id=pull_id)
    )).order_by(PoolItem.id).all()
    what = task.label + (f' · {category}' if category else '') + \
           (f' · {difficulty}' if difficulty else '')
    return jsonify({
        'message': f'{claimed} {what} prompt(s) are now yours.' if claimed else
                   f'Nothing unclaimed is left in {what} right now.',
        'claimed': claimed,
        'task_id': task.id,
        'language': task.language,
        'class': task.class_label,
        'category': category or None,
        'difficulty': difficulty or None,
        'pull_id': pull_id,
        'items': [_serialize_item(i) for i in items],
    }), 200


@app.route('/api/pool/items', methods=['GET'])
@token_required
def pool_my_items(current_user):
    """The annotator's own working set: everything currently claimed by them, plus (optionally) what they have already finished."""
    team = _pool_team()
    rater = _current_rater(current_user)
    if not (team and rater):
        return jsonify({'items': []}), 200

    scope = (request.args.get('scope') or 'open').lower()
    q = PoolItem.query.filter(PoolItem.team_id == team.id)
    # Narrow to one pull or one task when the annotator opened a specific slice.
    if request.args.get('pull_id'):
        q = q.filter(PoolItem.pull_id == request.args['pull_id'])
    if request.args.get('task_id', type=int):
        q = q.filter(PoolItem.task_id == request.args.get('task_id', type=int))
    if scope == 'done':
        q = q.filter(PoolItem.completed_by == rater.id,
                     PoolItem.status.in_(['completed', 'flagged']))
        q = q.order_by(PoolItem.completed_at.desc())
        limit = min(int(request.args.get('limit', 200)), 1000)
        items = q.limit(limit).all()
    else:
        q = q.filter(PoolItem.claimed_by == rater.id, PoolItem.status == 'claimed')
        items = q.order_by(PoolItem.id).all()

    # Whether each prompt needs a difficulty label (admin-controlled per language/class/category).
    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    out = []
    for i in items:
        d = _serialize_item(i)
        d['need_difficulty'] = difficulty_required_for(team, tasks.get(i.task_id), i.category)
        out.append(d)
    return jsonify({'items': out, 'count': len(items)}), 200


@app.route('/api/pool/submit', methods=['POST'])
@token_required
def pool_submit(current_user):
    """Save one item's annotation: corrected text + difficulty, or a flag."""
    data = request.get_json(silent=True) or {}
    rater = _current_rater(current_user)
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404

    item_id = data.get('item_id')
    item = PoolItem.query.get(item_id) if item_id else None
    if item is None:
        return jsonify({'message': 'Item not found'}), 404
    if item.claimed_by != rater.id and item.completed_by != rater.id:
        return jsonify({'message': 'This item is not assigned to you.'}), 403

    # Captured BEFORE the status changes below: is this a fresh submission or an edit of one they already made?
    is_edit = (item.completed_by == rater.id
               and item.completed_at is not None
               and item.status in ('completed', 'flagged'))

    flagged = bool(data.get('is_flagged'))
    text_in = data.get('text')
    difficulty = (data.get('difficulty') or '').strip().title()
    # The admin decides whether this slice (language/class/category) carries a difficulty label.
    item_team = Team.query.get(item.team_id)
    item_task = PoolTask.query.get(item.task_id) if item.task_id else None
    need_difficulty = difficulty_required_for(item_team, item_task, item.category)

    # A prompt takes exactly N answers and no more. Anyone who already answered it
    # may still edit their own; a newcomer arriving after it filled up is turned
    # away rather than silently making an (N+1)th answer.
    _target = annotations_target(item_team, item_task)
    _mine = PoolAnnotation.query.filter_by(item_id=item.id, rater_id=rater.id).first()
    _answered = PoolAnnotation.query.filter(
        PoolAnnotation.item_id == item.id,
        PoolAnnotation.status.in_(['completed', 'flagged'])).count()
    if _answered >= _target and not (_mine and _mine.status in ('completed', 'flagged')):
        return jsonify({'message': 'This prompt already has all the answers it '
                                   f'needs ({_target}). It has been returned to '
                                   'the pool for someone else.'}), 409

    # Both branches feed one annotation row below, so every name it reads exists
    # on both paths.
    reason, cleaned, results = '', '', None
    if flagged:
        reason = (data.get('flag_reason') or '').strip()
        if not reason:
            return jsonify({'message': 'Please pick a reason for flagging this item.'}), 400
        item.is_flagged = True
        item.flag_reason = reason[:255]
        item.status = 'flagged'
    else:
        if need_difficulty and difficulty not in DIFFICULTIES:
            return jsonify({'message': f'Difficulty must be one of {", ".join(DIFFICULTIES)}.'}), 400
        if difficulty and difficulty not in DIFFICULTIES:
            return jsonify({'message': f'Difficulty must be one of {", ".join(DIFFICULTIES)}.'}), 400
        # Score-based task types rate the item instead of editing its text.
        results = data.get('results')
        if (item.task_type or '') == 'audio-mdfs':
            results = valid_mdfs_results(results)
            if results is None:
                return jsonify({'message': 'Please rate all four dimensions (1–4).'}), 400
        cleaned = (text_in if text_in is not None else item.text).strip()
        if not cleaned:
            return jsonify({'message': 'The text cannot be empty.'}), 400
        item.final_text = cleaned
        item.is_edited = cleaned != (item.text or '').strip()
        item.final_difficulty = difficulty or None
        item.is_flagged = False
        item.flag_reason = None
        item.status = 'completed'
        if isinstance(results, dict):
            # A NEW dict (never in-place mutation), so SQLAlchemy sees the JSON change.
            item.extra_json = {**(item.extra_json or {}), 'results': results}
    _ann_payload = dict(
        final_text=(None if flagged else cleaned),
        final_difficulty=(None if flagged else (difficulty or None)),
        is_edited=(False if flagged else cleaned != (item.text or '').strip()),
        is_flagged=bool(flagged),
        flag_reason=(reason[:255] if flagged else None),
        results_json=(results if (not flagged and isinstance(results, dict)) else None),
        status=('flagged' if flagged else 'completed'),
    )

    notes = (data.get('notes') or '').strip()
    item.notes = notes[:2000] if notes else None

    # This annotator's own answer. Several people may answer the same prompt, so it
    # goes in their own row -- writing it onto the item would overwrite whoever
    # answered before them. The row already exists from the pull.
    ann = PoolAnnotation.query.filter_by(item_id=item.id, rater_id=rater.id).first()
    if ann is None:
        ann = PoolAnnotation(item_id=item.id, rater_id=rater.id, team_id=item.team_id,
                             task_id=item.task_id, pull_id=item.pull_id,
                             claimed_at=item.claimed_at, revision=0)
        db.session.add(ann)
    for k, v in _ann_payload.items():
        setattr(ann, k, v)
    ann.notes = notes[:2000] if notes else None
    if not is_edit:
        ann.completed_at = datetime.utcnow()
    ann.revision = (ann.revision or 0) + 1
    if 'time_taken_ms' in data:
        try:
            ann.time_taken_ms = max(0, min(int(data.get('time_taken_ms') or 0),
                                           6 * 3600 * 1000))
        except (TypeError, ValueError):
            pass
    db.session.flush()

    # The prompt is only finished once it has as many answers as the project asks
    # for; short of that it goes back to the pool for a DIFFERENT annotator.
    refresh_item_state(item, annotations_target(item_team, item_task))
    # An EDIT of an already-submitted item keeps its original submission time, so daily output and payment reports do not shift; the revision counter records the edit.
    item.completed_by = rater.id
    if not is_edit:
        item.completed_at = datetime.utcnow()
    item.revision = (item.revision or 0) + 1
    if 'time_taken_ms' in data:      # absent on edits -- never wipe the original timing
        try:
            tt = int(data.get('time_taken_ms') or 0)
            item.time_taken_ms = max(0, min(tt, 6 * 3600 * 1000))
        except (TypeError, ValueError):
            pass

    # A pull with nothing claimed left is finished; recording that keeps the annotator's "current work" list honest without touching a single prompt.
    close_finished_pulls(rater.id)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_submit failed: {e}")
        return jsonify({'message': 'Could not save. Please try again.'}), 500

    remaining = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == item.team_id, PoolItem.claimed_by == rater.id,
        PoolItem.status == 'claimed').scalar() or 0
    return jsonify({'message': 'Saved', 'item': _serialize_item(item),
                    'remaining_in_batch': remaining}), 200


@app.route('/api/pool/release', methods=['POST'])
@token_required
def pool_release(current_user):
    """Hand unfinished prompts back to the pool so they can be handed out again."""
    data = request.get_json(silent=True) or {}
    rater = _current_rater(current_user)
    if not rater:
        return jsonify({'message': 'Not found'}), 404

    # all_teams: the sign-out sweep -- every unfinished prompt this annotator holds, in every pool, goes back; everything submitted stays theirs.
    if data.get('all_teams'):
        mine = PoolItem.query.filter(PoolItem.claimed_by == rater.id,
                                     PoolItem.status == 'claimed').all()
        touched = {it.pull_id for it in mine if it.pull_id}
        n = release_claims(mine, rater_id=rater.id)
        if touched:
            now = datetime.utcnow()
            for pull in PoolPull.query.filter(PoolPull.pull_id.in_(list(touched)),
                                              PoolPull.status == 'open').all():
                pull.status = 'released'
                pull.released_at = now
        close_finished_pulls(rater.id)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"pool_release(all_teams) failed: {e}")
            return jsonify({'message': 'Could not release those items.'}), 500
        return jsonify({'message': f'{n} prompt(s) returned to the pool.', 'released': n}), 200

    team = _pool_team()
    if not team:
        return jsonify({'message': 'Not found'}), 404

    pull_key = (data.get('pull_id') or '').strip()
    if pull_key:
        pull = PoolPull.query.filter_by(pull_id=pull_key, rater_id=rater.id).first()
        if pull is None:
            return jsonify({'message': 'That pull is not yours.'}), 403
        n = release_pull_items(pull, rater_id=rater.id)
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"pool_release(pull) failed: {e}")
            return jsonify({'message': 'Could not return that pull.'}), 500
        return jsonify({'message': f'{n} prompt(s) returned to the pool.',
                        'released': n, 'pull_id': pull_key}), 200

    q = PoolItem.query.filter(PoolItem.team_id == team.id,
                              PoolItem.claimed_by == rater.id,
                              PoolItem.status == 'claimed')
    ids = data.get('item_ids')
    if ids:
        q = q.filter(PoolItem.id.in_([int(i) for i in ids]))
    n = release_claims(q.all(), rater_id=rater.id)
    close_finished_pulls(rater.id)
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_release failed: {e}")
        return jsonify({'message': 'Could not release those items.'}), 500
    return jsonify({'message': f'{n} prompt(s) returned to the pool.', 'released': n}), 200


@app.route('/api/pool/my_stats', methods=['GET'])
@token_required
def pool_my_stats(current_user):
    """The annotator's own progress: totals, per-language, and the last 30 days."""
    team = _pool_team()
    rater = _current_rater(current_user)
    if not (team and rater):
        return jsonify({'enabled': False}), 200

    rows = db.session.query(
        PoolItem.language, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             db.or_(PoolItem.claimed_by == rater.id,
                    PoolItem.completed_by == rater.id)
             ).group_by(PoolItem.language, PoolItem.status).all()

    by_lang = {}
    for lang, status, cnt in rows:
        slot = by_lang.setdefault(lang, {'language': lang, 'claimed': 0,
                                         'completed': 0, 'flagged': 0, 'edited': 0})
        if status in slot:
            slot[status] = cnt

    for lang, cnt in db.session.query(PoolItem.language, func.count(PoolItem.id)).filter(
        PoolItem.completed_by == rater.id, PoolItem.is_edited == True  # noqa: E712
    ).group_by(PoolItem.language).all():
        if lang in by_lang:
            by_lang[lang]['edited'] = cnt

    daily = {}
    since = datetime.utcnow() - timedelta(days=31)
    for (ts,) in db.session.query(PoolItem.completed_at).filter(
        PoolItem.completed_by == rater.id, PoolItem.completed_at >= since
    ).all():
        d = _ist_day(ts)
        if d:
            daily[d] = daily.get(d, 0) + 1
    series = sorted(({'date': d, 'count': c} for d, c in daily.items()),
                    key=lambda x: x['date'], reverse=True)

    total_done = sum(v['completed'] + v['flagged'] for v in by_lang.values())
    return jsonify({
        'enabled': True,
        'by_language': sorted(by_lang.values(), key=lambda x: x['language']),
        'total_completed': sum(v['completed'] for v in by_lang.values()),
        'total_flagged': sum(v['flagged'] for v in by_lang.values()),
        'total_edited': sum(v['edited'] for v in by_lang.values()),
        'total_done': total_done,
        'today': next((s['count'] for s in series if s['date'] == _today_ist()), 0),
        'daily': series[:30],
    }), 200


# Admin endpoints

def _admin_pool_team(current_user):
    """(team, error_response). A team admin is pinned to their own team."""
    if not _is_admin(current_user):
        return None, (jsonify({'message': 'Unauthorized'}), 401)
    scope, team_id = _admin_scope(current_user)
    if scope == 'team':
        team = Team.query.get(team_id)
    else:
        team = _pool_team()
    if team is None:
        return None, (jsonify({'message': 'Team not found'}), 404)
    if team.workflow != 'pool':
        return None, (jsonify({'message': f'{team.name} does not use the pool workflow.'}), 400)
    return team, None


@app.route('/api/pool/admin/dashboard', methods=['GET'])
@token_required
def pool_admin_dashboard(current_user):
    """The pool dashboard payload: org-level KPIs, then LANGUAGE stats with the CLASS breakdown nested inside each language, plus category/difficulty splits and."""
    release_stale_claims()
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    t0 = time.time()

    # --- 1. every (language, class, category, status) count in ONE query ---
    rows = db.session.query(
        PoolItem.language, PoolItem.class_label, PoolItem.category,
        PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id).group_by(
        PoolItem.language, PoolItem.class_label, PoolItem.category, PoolItem.status
    ).all()

    def _blank(**extra):
        d = {'total': 0, 'available': 0, 'claimed': 0, 'completed': 0, 'flagged': 0}
        d.update(extra)
        return d

    languages = {}
    totals = _blank()
    for lang, klass, cat, status, cnt in rows:
        lang = lang or 'Unknown'
        klass = str(klass) if klass not in (None, '') else 'Unspecified'
        cat = cat or 'other'

        L = languages.setdefault(lang, _blank(language=lang, classes={}, categories={}))
        K = L['classes'].setdefault(klass, _blank(**{'class': klass, 'categories': {}}))
        C = K['categories'].setdefault(cat, _blank(category=cat))
        LC = L['categories'].setdefault(cat, _blank(category=cat))

        for bucket in (totals, L, K, C, LC):
            bucket['total'] += cnt
            if status in bucket:
                bucket[status] += cnt

    # --- 2. difficulty distribution (source vs. what annotators decided) ---
    def _dist(col, only_done=True):
        q = db.session.query(PoolItem.language, col, func.count(PoolItem.id)).filter(
            PoolItem.team_id == team.id)
        if only_done:
            q = q.filter(PoolItem.status == 'completed')
        out = {}
        for lang, val, cnt in q.group_by(PoolItem.language, col).all():
            out.setdefault(lang or 'Unknown', {})[(val or 'Unset')] = cnt
        return out

    final_difficulty = _dist(PoolItem.final_difficulty, only_done=True)
    source_difficulty = _dist(PoolItem.source_difficulty, only_done=False)

    # How often annotators disagreed with the generated difficulty.
    changed = db.session.query(PoolItem.language, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.status == 'completed',
        PoolItem.final_difficulty.isnot(None),
        PoolItem.source_difficulty.isnot(None),
        PoolItem.final_difficulty != PoolItem.source_difficulty,
    ).group_by(PoolItem.language).all()
    difficulty_changed = {lang or 'Unknown': cnt for lang, cnt in changed}

    edited = db.session.query(PoolItem.language, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.is_edited == True  # noqa: E712
    ).group_by(PoolItem.language).all()
    edited_by_lang = {lang or 'Unknown': cnt for lang, cnt in edited}

    for lang, L in languages.items():
        L['final_difficulty'] = final_difficulty.get(lang, {})
        L['source_difficulty'] = source_difficulty.get(lang, {})
        L['difficulty_changed'] = difficulty_changed.get(lang, 0)
        L['edited'] = edited_by_lang.get(lang, 0)
        L['done'] = L['completed'] + L['flagged']
        L['progress'] = round(100.0 * L['done'] / L['total'], 1) if L['total'] else 0.0
        L['classes'] = sorted(
            ({**k,
              'done': k['completed'] + k['flagged'],
              'progress': round(100.0 * (k['completed'] + k['flagged']) / k['total'], 1)
                          if k['total'] else 0.0,
              'categories': sorted(k['categories'].values(), key=lambda c: c['category'])}
             for k in L['classes'].values()),
            key=lambda k: (len(k['class']), k['class']))
        L['categories'] = sorted(L['categories'].values(), key=lambda c: c['category'])

    # --- 3. per-annotator productivity ---
    member_rows = TeamMember.query.filter_by(team_id=team.id).all()
    members = {m.rater_id: m for m in member_rows}
    rater_ids = list(members.keys())
    raters = {r.id: r for r in Rater.query.filter(Rater.id.in_(rater_ids)).all()} if rater_ids else {}

    prod = {}
    for rid, status, cnt in db.session.query(
        PoolItem.completed_by, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             PoolItem.completed_by.isnot(None)).group_by(
                 PoolItem.completed_by, PoolItem.status).all():
        slot = prod.setdefault(rid, {'completed': 0, 'flagged': 0, 'claimed': 0,
                                     'edited': 0, 'languages': {}, 'last_active': None,
                                     'seconds': 0.0})
        if status in slot:
            slot[status] += cnt

    for rid, cnt in db.session.query(PoolItem.claimed_by, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.status == 'claimed'
    ).group_by(PoolItem.claimed_by).all():
        if rid is not None:
            prod.setdefault(rid, {'completed': 0, 'flagged': 0, 'claimed': 0,
                                  'edited': 0, 'languages': {}, 'last_active': None,
                                  'seconds': 0.0})['claimed'] = cnt

    for rid, cnt in db.session.query(PoolItem.completed_by, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.is_edited == True  # noqa: E712
    ).group_by(PoolItem.completed_by).all():
        if rid in prod:
            prod[rid]['edited'] = cnt

    for rid, lang, cnt in db.session.query(
        PoolItem.completed_by, PoolItem.language, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             PoolItem.completed_by.isnot(None)).group_by(
                 PoolItem.completed_by, PoolItem.language).all():
        if rid in prod:
            prod[rid]['languages'][lang] = cnt

    for rid, last, secs in db.session.query(
        PoolItem.completed_by, func.max(PoolItem.completed_at),
        func.sum(PoolItem.time_taken_ms)
    ).filter(PoolItem.team_id == team.id,
             PoolItem.completed_by.isnot(None)).group_by(PoolItem.completed_by).all():
        if rid in prod:
            prod[rid]['last_active'] = last.isoformat() if last else None
            prod[rid]['seconds'] = round((secs or 0) / 1000.0, 1)

    today = _today_ist()
    today_counts = {}
    since = datetime.utcnow() - timedelta(days=2)
    for rid, ts in db.session.query(PoolItem.completed_by, PoolItem.completed_at).filter(
        PoolItem.team_id == team.id, PoolItem.completed_at >= since
    ).all():
        if rid and _ist_day(ts) == today:
            today_counts[rid] = today_counts.get(rid, 0) + 1

    # Which tasks each annotator currently holds -- the ASR equivalent of the TTS "assigned batches" chips, and what makes an idle annotator "stale".
    held = {}
    for rows in active_assignments(team.id).values():
        for a, _r in rows:
            slot = held.setdefault(a.rater_id, [])
            if a.task_id not in slot:
                slot.append(a.task_id)

    annotators = []
    for rid, m in members.items():
        r = raters.get(rid)
        p = prod.get(rid, {'completed': 0, 'flagged': 0, 'claimed': 0, 'edited': 0,
                           'languages': {}, 'last_active': None, 'seconds': 0.0})
        done = p['completed'] + p['flagged']
        annotators.append({
            'rater_id': rid,
            'name': r.name if r else f'Annotator #{rid}',
            'email': r.email if r else '',
            'gender': getattr(r, 'gender', '') if r else '',
            'age': getattr(r, 'age', None) if r else None,
            'is_active': bool(getattr(r, 'is_active', True)) and bool(m.is_active),
            'account_active': bool(getattr(r, 'is_active', True)) if r else False,
            'assigned_task_ids': sorted(held.get(rid, [])),
            'allowed_languages': [x.strip() for x in (m.languages or '').split(',') if x.strip()],
            'pull_size': m.pull_size,
            'completed': p['completed'],
            'flagged': p['flagged'],
            'edited': p['edited'],
            'in_progress': p['claimed'],
            'done': done,
            'today': today_counts.get(rid, 0),
            'languages': p['languages'],
            'last_active': p['last_active'],
            'avg_seconds': round(p['seconds'] / done, 1) if done else 0.0,
        })
    annotators.sort(key=lambda a: (-a['done'], a['name']))

    # --- 4. daily throughput for the team (last 30 IST days) ---
    daily = {}
    since30 = datetime.utcnow() - timedelta(days=31)
    for (ts,) in db.session.query(PoolItem.completed_at).filter(
        PoolItem.team_id == team.id, PoolItem.completed_at >= since30
    ).all():
        d = _ist_day(ts)
        if d:
            daily[d] = daily.get(d, 0) + 1
    daily_series = sorted(({'date': d, 'count': c} for d, c in daily.items()),
                          key=lambda x: x['date'], reverse=True)[:30]

    uploads = [{'id': u.id, 'name': u.name, 'source': u.source,
                'item_count': u.item_count,
                'created_at': u.created_at.isoformat() if u.created_at else None}
               for u in PoolUpload.query.filter_by(team_id=team.id)
               .order_by(PoolUpload.id.desc()).all()]

    stale = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.status == 'claimed',
        PoolItem.claimed_at < datetime.utcnow() - timedelta(hours=STALE_CLAIM_HOURS)
    ).scalar() or 0

    totals['done'] = totals['completed'] + totals['flagged']
    totals['progress'] = round(100.0 * totals['done'] / totals['total'], 1) if totals['total'] else 0.0
    totals['edited'] = sum(edited_by_lang.values())
    totals['difficulty_changed'] = sum(difficulty_changed.values())
    totals['annotators'] = len(annotators)
    totals['active_annotators'] = sum(1 for a in annotators if a['done'] > 0)
    totals['completed_today'] = sum(today_counts.values())
    totals['stale_claims'] = stale
    totals['languages'] = len(languages)

    return jsonify({
        'team': _serialize_team(team),
        'organization': ORG_NAME,
        'stats': totals,
        'languages': sorted(languages.values(), key=lambda l: l['language']),
        'annotators': annotators,
        'daily': daily_series,
        'uploads': uploads,
        'difficulties': DIFFICULTIES,
        'settings': {'difficulty_annotation':
                     bool(team_setting(team, 'difficulty_annotation', True)),
                     'max_open_items': open_items_cap(team)},
        'stale_claim_hours': STALE_CLAIM_HOURS,
        'generated_in_ms': int((time.time() - t0) * 1000),
    }), 200


@app.route('/api/pool/admin/settings', methods=['POST'])
@token_required
def pool_admin_settings(current_user):
    """Flip a team-level behaviour switch (e.g. whether annotators label difficulty). Body: {'difficulty_annotation': true/false, ...} -- unknown keys are stored as-is so a future switch needs no API change."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    updates = {k: v for k, v in data.items() if k != 'team'}
    if not updates:
        return jsonify({'message': 'Nothing to change.'}), 400
    merged = dict(team.settings or {})
    merged.update(updates)
    team.settings = merged
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_admin_settings failed: {e}")
        return jsonify({'message': 'Could not save that setting.'}), 500
    return jsonify({'message': 'Settings saved.', 'settings': merged}), 200


@app.route('/api/pool/admin/items', methods=['GET'])
@token_required
def pool_admin_items(current_user):
    """Paginated, filterable browse over the pool (the admin's data explorer)."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    q = PoolItem.query.filter(PoolItem.team_id == team.id)
    args = request.args
    if args.get('task_id', type=int):
        q = q.filter(PoolItem.task_id == args.get('task_id', type=int))
    if args.get('language'):
        q = q.filter(PoolItem.language == args['language'])
    if args.get('class'):
        q = q.filter(PoolItem.class_label == args['class'])
    if args.get('category'):
        q = q.filter(PoolItem.category == args['category'])
    if args.get('task_type'):
        q = q.filter(PoolItem.task_type == args['task_type'])
    if args.get('status'):
        q = q.filter(PoolItem.status == args['status'])
    if args.get('difficulty'):
        q = q.filter(PoolItem.final_difficulty == args['difficulty'])
    if args.get('annotator', type=int):
        q = q.filter(PoolItem.completed_by == args.get('annotator', type=int))
    if args.get('edited') in ('1', 'true'):
        q = q.filter(PoolItem.is_edited == True)  # noqa: E712
    if args.get('flagged') in ('1', 'true'):
        q = q.filter(PoolItem.is_flagged == True)  # noqa: E712
    search = (args.get('q') or '').strip()
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(PoolItem.text.like(like), PoolItem.final_text.like(like)))

    total = q.count()
    page = max(1, args.get('page', 1, type=int))
    per_page = min(max(1, args.get('per_page', 50, type=int)), 500)
    items = q.order_by(PoolItem.id).offset((page - 1) * per_page).limit(per_page).all()

    names = {}
    ids = {i.completed_by for i in items if i.completed_by}
    if ids:
        names = {r.id: r.name for r in Rater.query.filter(Rater.id.in_(ids)).all()}

    out = []
    for i in items:
        d = _serialize_item(i)
        d['annotator'] = names.get(i.completed_by)
        out.append(d)
    return jsonify({'items': out, 'total': total, 'page': page,
                    'per_page': per_page,
                    'pages': (total + per_page - 1) // per_page}), 200


@app.route('/api/pool/admin/member', methods=['POST'])
@token_required
def pool_admin_member(current_user):
    """Add an annotator to the pool team, or change the languages / batch size they are handed."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    rater_id = data.get('rater_id')
    rater = Rater.query.get(rater_id) if rater_id else None
    if rater is None:
        return jsonify({'message': 'Annotator not found'}), 404

    m = TeamMember.query.filter_by(team_id=team.id, rater_id=rater.id).first()
    if data.get('remove'):
        if m is None:
            return jsonify({'message': 'Not a member.'}), 200
        held = PoolItem.query.filter_by(team_id=team.id, claimed_by=rater.id,
                                        status='claimed').all()
        release_claims(held, rater_id=rater.id)   # untouched work goes back to the pool
        # Their tasks go back on the shelf, otherwise a task nobody can work on would still count as taken and no one else could ever be given it.
        freed = _revoke_assignments(team.id, rater_id=rater.id)
        close_finished_pulls(rater.id)
        m.is_active = False
        db.session.commit()
        return jsonify({'message': f'{rater.name} removed from {team.name}; '
                                   f'{len(held)} unfinished prompt(s) returned to the pool '
                                   f'and {freed} task(s) unassigned.'}), 200

    if m is None:
        m = TeamMember(team_id=team.id, rater_id=rater.id, role='annotator')
        db.session.add(m)
    m.is_active = True
    if 'languages' in data:
        langs = data.get('languages') or []
        if isinstance(langs, str):
            langs = [x.strip() for x in langs.split(',')]
        m.languages = ','.join([x.strip() for x in langs if x and x.strip()])
    if data.get('pull_size'):
        try:
            m.pull_size = max(1, min(int(data['pull_size']), 500))
        except (TypeError, ValueError):
            pass
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"pool_admin_member failed: {e}")
        return jsonify({'message': 'Could not save that change.'}), 500
    return jsonify({'message': f'{rater.name} updated for {team.name}.',
                    'member': {'rater_id': rater.id, 'name': rater.name,
                               'languages': [x for x in (m.languages or '').split(',') if x],
                               'pull_size': m.pull_size}}), 200


@app.route('/api/pool/admin/candidates', methods=['GET'])
@token_required
def pool_admin_candidates(current_user):
    """Annotators who could be added to this team (everyone not already in it)."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    in_team = {m.rater_id for m in TeamMember.query.filter_by(team_id=team.id, is_active=True).all()}
    out = [{'id': r.id, 'name': r.name, 'email': r.email}
           for r in Rater.query.order_by(Rater.name).all()
           if r.id not in in_team and getattr(r, 'is_active', True)]
    return jsonify({'candidates': out,
                    'languages': [row[0] for row in db.session.query(PoolItem.language)
                                  .filter(PoolItem.team_id == team.id).distinct()
                                  .order_by(PoolItem.language).all()]}), 200


@app.route('/api/pool/admin/reclaim', methods=['POST'])
@token_required
def pool_admin_reclaim(current_user):
    """Sweep abandoned claims (claimed but untouched for STALE_CLAIM_HOURS) back into the pool."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    try:
        hours = int(data.get('hours') or STALE_CLAIM_HOURS)
    except (TypeError, ValueError):
        hours = STALE_CLAIM_HOURS
    cutoff = datetime.utcnow() - timedelta(hours=max(1, hours))
    q = PoolItem.query.filter(PoolItem.team_id == team.id, PoolItem.status == 'claimed',
                              PoolItem.claimed_at < cutoff)
    if data.get('rater_id'):
        q = q.filter(PoolItem.claimed_by == int(data['rater_id']))
    stale = q.all()
    touched = {it.claimed_by for it in stale if it.claimed_by}
    n = release_claims(stale)
    for rid in touched:
        close_finished_pulls(rid)
    db.session.commit()
    return jsonify({'message': f'{n} stale claim(s) returned to the pool.', 'released': n}), 200


# Export with real progress (the UI shows a live bar instead of freezing)

# Export jobs must be visible to EVERY gunicorn worker: the browser starts the job on one worker and then polls status / downloads from whichever worker the next.
_EXPORT_JOBS = {}
_EXPORT_LOCK = threading.Lock()
_EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           'exports', 'pool')
_EXPORT_JOB_DIR = os.path.join(_EXPORT_DIR, 'jobs')

# Finished exports (and their job files) are swept after this many hours.
EXPORT_TTL_HOURS = int(os.environ.get('POOL_EXPORT_TTL_HOURS', '24'))


def _job_path(job_id):
    return os.path.join(_EXPORT_JOB_DIR, f'{job_id}.json')


def _job_save(job):
    """Publish job state so any worker can read it."""
    import json as _json
    os.makedirs(_EXPORT_JOB_DIR, exist_ok=True)
    tmp = _job_path(job['id']) + f'.{os.getpid()}.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            _json.dump(job, fh)
        os.replace(tmp, _job_path(job['id']))
    except Exception as e:
        app.logger.error(f'could not persist export job {job.get("id")}: {e}')


def _job_load(job_id):
    import json as _json
    with _EXPORT_LOCK:
        cached = dict(_EXPORT_JOBS.get(job_id) or {})
    if cached:
        return cached
    try:
        with open(_job_path(job_id), encoding='utf-8') as fh:
            return _json.load(fh)
    except Exception:
        return {}


def _job_update(job_id, **fields):
    with _EXPORT_LOCK:
        job = _EXPORT_JOBS.setdefault(job_id, {'id': job_id})
        job.update(fields)
        snapshot = dict(job)
    _job_save(snapshot)
    return snapshot


def _export_sweep():
    """Delete generated files and job records older than EXPORT_TTL_HOURS so the exports directory cannot grow without bound."""
    cutoff = time.time() - EXPORT_TTL_HOURS * 3600
    for folder in (_EXPORT_DIR, _EXPORT_JOB_DIR):
        try:
            for name in os.listdir(folder):
                path = os.path.join(folder, name)
                if os.path.isfile(path) and os.path.getmtime(path) < cutoff:
                    os.remove(path)
        except Exception:
            pass

# The full record of one prompt: what it was, what came back, and everything needed to trace it -- which task it belongs to, who the task belongs to, which pull.
EXPORT_COLUMNS = [
    'Item ID', 'Task ID', 'Task', 'Task Assigned To', 'Team', 'Task Type', 'Upload',
    'Language', 'Class', 'Category', 'Source', 'Words',
    'Original Text', 'Final Text', 'Edited',
    'Source Difficulty', 'Final Difficulty', 'Difficulty Changed',
    'Status', 'Flagged', 'Flag Reason', 'Notes',
    'Annotator', 'Annotator Email', 'Pull ID',
    'Claimed At (IST)', 'Completed At (IST)', 'Seconds Spent', 'Revisions',
    'MDFS Expression', 'MDFS Phrasing', 'MDFS Smoothness', 'MDFS Pacing',
    'Extra Metadata (JSON)',
]


def _export_row(it, who, team_name='', upload_name='', task=None, holder=''):
    """One fully-described row: what the task was, what the annotator changed, who did it and exactly when."""
    final = it.final_text if it.final_text is not None else ''
    name, email = (who or ('', ''))
    extra = it.extra_json
    # The MDFS scores get their own columns; everything else stays in the JSON blob.
    scores = (extra or {}).get('results') if isinstance(extra, dict) else None
    scores = scores if isinstance(scores, dict) else {}
    if isinstance(extra, (dict, list)):
        try:
            extra = json.dumps(extra, ensure_ascii=False)
        except (TypeError, ValueError):
            extra = str(extra)
    return [
        it.id, it.task_id, task.label if task else '', holder,
        team_name, task_type_label(it.task_type), upload_name,
        it.language, it.class_label, it.category, it.source, it.n_words,
        it.text, final, 'yes' if it.is_edited else 'no',
        it.source_difficulty or '', it.final_difficulty or '',
        'yes' if (it.final_difficulty and it.source_difficulty
                  and it.final_difficulty != it.source_difficulty) else 'no',
        it.status, 'yes' if it.is_flagged else 'no', it.flag_reason or '',
        (it.notes or '').replace('\n', ' '),
        name, email, it.pull_id or '',
        _ist_stamp(it.claimed_at), _ist_stamp(it.completed_at),
        round((it.time_taken_ms or 0) / 1000.0, 1), it.revision or 0,
        *[scores.get(dim, '') for dim in MDFS_DIMENSIONS],
        extra or '',
    ]


def _run_export(job_id, team_id, filters, fmt, flask_app):
    """Background worker: streams the pool to CSV/XLSX, updating job progress."""
    with flask_app.app_context():
        try:
            q = PoolItem.query.filter(PoolItem.team_id == team_id)
            for field, col in [('language', PoolItem.language), ('class', PoolItem.class_label),
                               ('category', PoolItem.category), ('status', PoolItem.status),
                               ('difficulty', PoolItem.final_difficulty),
                               ('task_id', PoolItem.task_id),
                               ('task_type', PoolItem.task_type)]:
                if filters.get(field):
                    q = q.filter(col == filters[field])
            if filters.get('only_done'):
                q = q.filter(PoolItem.status.in_(['completed', 'flagged']))

            total = q.count()
            _job_update(job_id, total=total, status='running')

            names = {r.id: (r.name, r.email or '') for r in Rater.query.all()}
            team_row = Team.query.get(team_id)
            team_name = team_row.name if team_row else ''
            uploads = {u.id: u.name for u in PoolUpload.query.filter_by(team_id=team_id).all()}
            tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team_id).all()}
            holders = {}
            for tid, rows in active_assignments(team_id).items():
                names_list = [(r.name if r else '') + (f' ({a.category})' if a.category else '')
                              for a, r in rows]
                holders[tid] = ' | '.join(n for n in names_list if n)
            os.makedirs(_EXPORT_DIR, exist_ok=True)
            ts = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            base = f"asr_pool_export_{ts}_{job_id[:8]}"

            done = 0
            if fmt == 'xlsx':
                import openpyxl
                wb = openpyxl.Workbook(write_only=True)
                ws = wb.create_sheet('Pool')
                ws.append(EXPORT_COLUMNS)
                for it in q.order_by(PoolItem.id).yield_per(1000):
                    ws.append(_export_row(it, names.get(it.completed_by), team_name,
                                          uploads.get(it.upload_id, ''),
                                          tasks.get(it.task_id),
                                          holders.get(it.task_id, '')))
                    done += 1
                    if done % 500 == 0:
                        _job_update(job_id, done=done)
                path = os.path.join(_EXPORT_DIR, base + '.xlsx')
                wb.save(path)
            else:
                path = os.path.join(_EXPORT_DIR, base + '.csv')
                with open(path, 'w', encoding='utf-8-sig', newline='') as fh:
                    w = csv.writer(fh)
                    w.writerow(EXPORT_COLUMNS)
                    for it in q.order_by(PoolItem.id).yield_per(1000):
                        w.writerow(_export_row(it, names.get(it.completed_by), team_name,
                                               uploads.get(it.upload_id, ''),
                                               tasks.get(it.task_id),
                                               holders.get(it.task_id, '')))
                        done += 1
                        if done % 500 == 0:
                            _job_update(job_id, done=done)

            _job_update(job_id, status='done', done=done, path=path,
                        filename=os.path.basename(path), finished_at=time.time())
        except Exception as e:
            app.logger.error(f"pool export job {job_id} failed: {e}", exc_info=True)
            _job_update(job_id, status='error',
                        error='The export could not be generated. Please try again.')


@app.route('/api/pool/admin/export/start', methods=['POST'])
@token_required
def pool_export_start(current_user):
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    fmt = 'xlsx' if (data.get('format') or 'csv').lower() in ('xlsx', 'excel') else 'csv'
    _export_sweep()
    job_id = uuid.uuid4().hex
    _job_update(job_id, status='queued', done=0, total=0, format=fmt,
                started_at=time.time(), team_id=team.id)
    # Hand the worker the real app object (see _run_export).
    threading.Thread(target=_run_export,
                     args=(job_id, team.id, data, fmt, app._get_current_object()),
                     daemon=True).start()
    return jsonify({'job_id': job_id, 'status': 'queued'}), 202


@app.route('/api/pool/admin/export/status/<job_id>', methods=['GET'])
@token_required
def pool_export_status(current_user, job_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    job = _job_load(job_id)
    if not job:
        return jsonify({'message': 'That export has expired. Please start a new one.'}), 404
    job.pop('path', None)
    if job.get('total'):
        job['percent'] = min(100, round(100.0 * job.get('done', 0) / job['total'], 1))
    else:
        job['percent'] = 0
    return jsonify(job), 200


@app.route('/api/pool/admin/export/download/<job_id>', methods=['GET'])
@token_required
def pool_export_download(current_user, job_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    job = _job_load(job_id)
    if not job or job.get('status') != 'done':
        return jsonify({'message': 'That export is not ready yet.'}), 409
    if not job.get('path') or not os.path.exists(job['path']):
        return jsonify({'message': 'That export file has been cleaned up. '
                                   'Please start a new export.'}), 410
    return send_file(job['path'], as_attachment=True, download_name=job['filename'])


# Admin parity with the TTS dashboard The ASR admin gets the same reach into the work as the TTS admin has over batches: drill into any annotator, open any item.

@app.route('/api/pool/admin/annotator/<int:rater_id>', methods=['GET'])
@token_required
def pool_admin_annotator(current_user, rater_id):
    """Everything one annotator has done in this pool: totals, the breakdown by language/class/category/difficulty, day-by-day output, and their most recent items."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    rater = Rater.query.get(rater_id)
    if rater is None:
        return jsonify({'message': 'Annotator not found'}), 404
    if not _rater_in_scope(current_user, rater):
        return jsonify({'message': 'This annotator is not in your team.'}), 403

    member = TeamMember.query.filter_by(team_id=team.id, rater_id=rater_id).first()

    totals = {'completed': 0, 'flagged': 0, 'claimed': 0, 'edited': 0,
              'difficulty_changed': 0, 'seconds': 0.0}
    by_language = {}
    for lang, klass, status, cnt in db.session.query(
        PoolItem.language, PoolItem.class_label, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             db.or_(PoolItem.completed_by == rater_id, PoolItem.claimed_by == rater_id)
             ).group_by(PoolItem.language, PoolItem.class_label, PoolItem.status).all():
        L = by_language.setdefault(lang, {'language': lang, 'completed': 0, 'flagged': 0,
                                          'claimed': 0, 'classes': {}})
        K = L['classes'].setdefault(str(klass or '-'), {'class': str(klass or '-'),
                                                        'completed': 0, 'flagged': 0,
                                                        'claimed': 0})
        for slot in (L, K):
            if status in slot:
                slot[status] += cnt
        if status in totals:
            totals[status] += cnt

    for lang in by_language.values():
        lang['classes'] = sorted(lang['classes'].values(), key=lambda k: k['class'])

    totals['edited'] = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
        PoolItem.is_edited == True).scalar() or 0            # noqa: E712
    totals['difficulty_changed'] = db.session.query(func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
        PoolItem.final_difficulty.isnot(None), PoolItem.source_difficulty.isnot(None),
        PoolItem.final_difficulty != PoolItem.source_difficulty).scalar() or 0
    secs = db.session.query(func.sum(PoolItem.time_taken_ms)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id).scalar() or 0
    totals['seconds'] = round(secs / 1000.0, 1)

    categories = {c or 'other': n for c, n in db.session.query(
        PoolItem.category, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id
    ).group_by(PoolItem.category).all()}
    difficulties = {d or 'Unset': n for d, n in db.session.query(
        PoolItem.final_difficulty, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
        PoolItem.status == 'completed').group_by(PoolItem.final_difficulty).all()}

    daily = {}
    for (ts,) in db.session.query(PoolItem.completed_at).filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
        PoolItem.completed_at >= datetime.utcnow() - timedelta(days=31)).all():
        d = _ist_day(ts)
        if d:
            daily[d] = daily.get(d, 0) + 1

    recent = [_serialize_item(i) for i in PoolItem.query.filter(
        PoolItem.team_id == team.id, PoolItem.completed_by == rater_id
    ).order_by(PoolItem.completed_at.desc()).limit(100).all()]

    # Per-TASK breakdown: the ASR answer to the TTS "tasks per batch" drill-down.
    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    mine_tasks = {}
    for tid, status, cnt in db.session.query(
        PoolItem.task_id, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id, PoolItem.task_id.isnot(None),
             db.or_(PoolItem.completed_by == rater_id, PoolItem.claimed_by == rater_id)
             ).group_by(PoolItem.task_id, PoolItem.status).all():
        slot = mine_tasks.setdefault(tid, _blank_counts(task_id=tid))
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt
    for tid, secs, last in db.session.query(
        PoolItem.task_id, func.sum(PoolItem.time_taken_ms), func.max(PoolItem.completed_at)
    ).filter(PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
             PoolItem.task_id.isnot(None)).group_by(PoolItem.task_id).all():
        if tid in mine_tasks:
            mine_tasks[tid]['hours'] = round((secs or 0) / 3600000.0, 2)
            mine_tasks[tid]['last_active_ist'] = _ist_stamp(last)
    for tid, cnt in db.session.query(PoolItem.task_id, func.count(PoolItem.id)).filter(
            PoolItem.team_id == team.id, PoolItem.completed_by == rater_id,
            PoolItem.is_edited == True).group_by(PoolItem.task_id).all():   # noqa: E712
        if tid in mine_tasks:
            mine_tasks[tid]['edited'] = cnt

    held_ids = {a.task_id for rows in active_assignments(team.id).values()
                for a, _r in rows if a.rater_id == rater_id}
    by_task = []
    for tid, c in mine_tasks.items():
        t = tasks.get(tid)
        by_task.append(dict(_with_progress(c), label=t.label if t else f'Task #{tid}',
                            language=t.language if t else '',
                            **{'class': t.class_label if t else ''},
                            task_total=t.item_count if t else 0,
                            hours=c.get('hours', 0.0),
                            edited=c.get('edited', 0),
                            last_active_ist=c.get('last_active_ist', ''),
                            is_assigned=tid in held_ids))
    # Tasks they hold but have not started yet still belong in the list.
    for tid in held_ids - set(mine_tasks):
        t = tasks.get(tid)
        by_task.append(dict(_with_progress(_blank_counts(task_id=tid)),
                            label=t.label if t else f'Task #{tid}',
                            language=t.language if t else '',
                            **{'class': t.class_label if t else ''},
                            task_total=t.item_count if t else 0,
                            hours=0.0, edited=0, last_active_ist='', is_assigned=True))
    by_task.sort(key=lambda x: (-x['done'], x['task_id']))

    done = totals['completed'] + totals['flagged']
    return jsonify({
        'annotator': {'id': rater.id, 'name': rater.name, 'email': rater.email,
                      'is_active': bool(getattr(rater, 'is_active', True))},
        'by_task': by_task,
        'by_task_type': my_work_by_task_type(team.id, rater_id),
        'membership': {
            'languages': [x.strip() for x in ((member.languages if member else '') or '').split(',') if x.strip()],
            'pull_size': member.pull_size if member else None,
            'is_active': bool(member.is_active) if member else False,
            'joined': member.created_at.isoformat() if member and member.created_at else None,
        },
        'totals': dict(totals, done=done,
                       avg_seconds=round(totals['seconds'] / done, 1) if done else 0.0),
        'by_language': sorted(by_language.values(), key=lambda x: x['language']),
        'categories': categories,
        'difficulties': difficulties,
        'daily': sorted(({'date': d, 'count': c} for d, c in daily.items()),
                        key=lambda x: x['date'], reverse=True)[:30],
        'recent_items': recent,
    }), 200


@app.route('/api/pool/admin/item/<int:item_id>', methods=['GET'])
@token_required
def pool_admin_item(current_user, item_id):
    """One item in full: the original text, the annotator's version, the label and who did it -- the pool equivalent of opening a task in the TTS dashboard."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    it = PoolItem.query.filter_by(id=item_id, team_id=team.id).first()
    if it is None:
        return jsonify({'message': 'Item not found'}), 404
    ids = [x for x in (it.claimed_by, it.completed_by) if x]
    names = {r.id: r.name for r in Rater.query.filter(Rater.id.in_(ids)).all()} if ids else {}
    task = PoolTask.query.get(it.task_id) if it.task_id else None
    data = _serialize_item(it)
    data.update({
        'claimed_by': names.get(it.claimed_by),
        'completed_by': names.get(it.completed_by),
        'claimed_at': it.claimed_at.isoformat() if it.claimed_at else None,
        'time_taken_ms': it.time_taken_ms,
        'revision': it.revision,
        'upload_id': it.upload_id,
        'task_label': task.label if task else None,
        'extra': it.extra_json,
    })
    return jsonify({'item': data}), 200


@app.route('/api/pool/admin/item/<int:item_id>/reset', methods=['POST'])
@token_required
def pool_admin_item_reset(current_user, item_id):
    """Send one item back to the pool for someone to redo."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    it = PoolItem.query.filter_by(id=item_id, team_id=team.id).first()
    if it is None:
        return jsonify({'message': 'Item not found'}), 404
    was_held_by = it.claimed_by
    it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
    it.final_text = it.final_difficulty = None
    it.is_edited = it.is_flagged = False
    it.flag_reason = it.notes = None
    it.completed_by = it.completed_at = it.time_taken_ms = None
    if isinstance(it.extra_json, dict) and 'results' in it.extra_json:
        it.extra_json = {k: v for k, v in it.extra_json.items() if k != 'results'}
    if was_held_by:
        close_finished_pulls(was_held_by)
    db.session.commit()
    return jsonify({'message': f'Prompt #{item_id} is back in the pool.'}), 200


@app.route('/api/pool/admin/export_annotators_csv', methods=['GET'])
@token_required
def pool_export_annotators_csv(current_user):
    """Per-annotator productivity report -- the pool's answer to the TTS annotator export."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    members = TeamMember.query.filter_by(team_id=team.id).all()
    raters = {r.id: r for r in Rater.query.filter(
        Rater.id.in_([m.rater_id for m in members])).all()} if members else {}

    agg = {}
    for rid, status, cnt in db.session.query(
        PoolItem.completed_by, PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             PoolItem.completed_by.isnot(None)).group_by(
                 PoolItem.completed_by, PoolItem.status).all():
        agg.setdefault(rid, {})[status] = cnt
    edited = dict(db.session.query(PoolItem.completed_by, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.is_edited == True).group_by(   # noqa: E712
        PoolItem.completed_by).all())
    holding = dict(db.session.query(PoolItem.claimed_by, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.status == 'claimed').group_by(
        PoolItem.claimed_by).all())
    secs = dict(db.session.query(PoolItem.completed_by, func.sum(PoolItem.time_taken_ms)).filter(
        PoolItem.team_id == team.id).group_by(PoolItem.completed_by).all())
    last = dict(db.session.query(PoolItem.completed_by, func.max(PoolItem.completed_at)).filter(
        PoolItem.team_id == team.id).group_by(PoolItem.completed_by).all())
    langs = {}
    for rid, lang, cnt in db.session.query(
        PoolItem.completed_by, PoolItem.language, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id,
             PoolItem.completed_by.isnot(None)).group_by(
                 PoolItem.completed_by, PoolItem.language).all():
        langs.setdefault(rid, []).append(f'{lang}:{cnt}')

    # Payable work per kind of task: 'type:count (hours)' pairs per annotator.
    type_split = {}
    for rid, ttype, cnt, ms in db.session.query(
        PoolItem.completed_by, func.coalesce(PoolItem.task_type, 'text-review'),
        func.count(PoolItem.id), func.sum(func.coalesce(PoolItem.time_taken_ms, 0)),
    ).filter(PoolItem.team_id == team.id, PoolItem.completed_by.isnot(None),
             PoolItem.status.in_(['completed', 'flagged'])).group_by(
                 PoolItem.completed_by,
                 func.coalesce(PoolItem.task_type, 'text-review')).all():
        type_split.setdefault(rid, []).append(
            f'{ttype}:{cnt} ({round((ms or 0) / 3600000.0, 2)}h)')

    # Which tasks each annotator holds, so the report answers "who has what" as well as "who did how much".
    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    held = {}
    for rows in active_assignments(team.id).values():
        for a, _r in rows:
            slot = held.setdefault(a.rater_id, [])
            if a.task_id not in slot:
                slot.append(a.task_id)

    buf = io.StringIO()
    w = csv.writer(buf)
    first = dict(db.session.query(PoolItem.completed_by, func.min(PoolItem.completed_at)).filter(
        PoolItem.team_id == team.id).group_by(PoolItem.completed_by).all())
    w.writerow(['Sr. No.', 'Annotator', 'Email', 'Account', 'Done by type (count·h)',
                'Tasks assigned', 'Task IDs', 'Tasks held',
                'Languages allowed', 'Prompts per pull', 'Completed', 'Flagged',
                'Text edited', 'Holding now', 'Total done (payable)',
                'Total time (h)', 'Avg seconds/prompt', 'Languages worked',
                'First activity (IST)', 'Last activity (IST)'])
    rows = []
    for m in members:
        r = raters.get(m.rater_id)
        a = agg.get(m.rater_id, {})
        completed, flagged = a.get('completed', 0), a.get('flagged', 0)
        done = completed + flagged
        total_secs = (secs.get(m.rater_id) or 0) / 1000.0
        mine = sorted(held.get(m.rater_id, []))
        rows.append([
            r.name if r else f'#{m.rater_id}', r.email if r else '',
            'active' if (r and getattr(r, 'is_active', True) and m.is_active) else 'inactive',
            ' | '.join(sorted(type_split.get(m.rater_id, []))) or '-',
            len(mine), ' | '.join(f'#{t}' for t in mine),
            ' | '.join(tasks[t].label for t in mine if t in tasks),
            ' | '.join(x.strip() for x in (m.languages or '').split(',') if x.strip()) or 'all',
            m.pull_size, completed, flagged, edited.get(m.rater_id, 0),
            holding.get(m.rater_id, 0), done,
            round(total_secs / 3600.0, 2),
            round(total_secs / done, 1) if done else 0,
            ' | '.join(sorted(langs.get(m.rater_id, []))),
            _ist_stamp(first.get(m.rater_id)), _ist_stamp(last.get(m.rater_id)),
        ])
    rows.sort(key=lambda x: -x[13])
    for i, row in enumerate(rows, 1):
        w.writerow([i] + row)

    stamp = datetime.utcnow().strftime('%Y%m%d')
    return csv_response(buf, f'asr_annotators_{stamp}.csv')


@app.route('/api/pool/admin/export_tasks_csv', methods=['GET'])
@token_required
def pool_export_tasks_csv(current_user):
    """The pool's task list: one row per TASK x category, carrying the task id an admin quotes and who the task belongs to."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err

    tasks = {t.id: t for t in PoolTask.query.filter_by(team_id=team.id).all()}
    holders = active_assignments(team.id)

    rows = db.session.query(
        PoolItem.task_id, PoolItem.task_type, PoolItem.category,
        PoolItem.status, func.count(PoolItem.id)
    ).filter(PoolItem.team_id == team.id).group_by(
        PoolItem.task_id, PoolItem.task_type, PoolItem.category, PoolItem.status).all()

    grouped = {}
    for task_id, ttype, cat, status, cnt in rows:
        key = (task_id or 0, task_type_label(ttype), cat or 'other')
        slot = grouped.setdefault(key, _blank_counts())
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Sr. No.', 'Task ID', 'Task type', 'Language', 'Class', 'Category',
                'Assigned to', 'Total prompts', 'Available', 'In progress',
                'Completed', 'Flagged', 'Done %', 'Report generated (IST)'])
    stamp_now = _ist_stamp(datetime.utcnow())
    n = 0
    for (task_id, ttype, cat), v in sorted(
            grouped.items(), key=lambda kv: (kv[0][0], kv[0][2])):
        task = tasks.get(task_id)
        rows_for_task = holders.get(task_id, [])
        # The row is one (task, category): its holders are every whole-task assignee plus everyone assigned exactly this category.
        names = []
        for a, r in rows_for_task:
            if a.category is None or a.category == cat:
                nm = r.name if r else f'Annotator #{a.rater_id}'
                if nm not in names:
                    names.append(nm)
        holder_name = ' | '.join(names)
        n += 1
        done = v['completed'] + v['flagged']
        w.writerow([n, task_id or '', ttype,
                    task.language if task else '', task.class_label if task else '', cat,
                    holder_name,
                    v['total'], v['available'], v['claimed'],
                    v['completed'], v['flagged'],
                    round(100.0 * done / v['total'], 1) if v['total'] else 0, stamp_now])

    stamp = datetime.utcnow().strftime('%Y%m%d')
    return csv_response(buf, f'asr_task_list_{stamp}.csv')


# Activity log Every state change an item goes through carries its own timestamp on the row (claimed_at / completed_at), so the log is derived rather than.

def _activity_events(team, since=None, rater_id=None, limit=500):
    """Newest-first list of {when, event, item, language, class, category, annotator, detail}."""
    q = PoolItem.query.filter(PoolItem.team_id == team.id)
    if rater_id:
        q = q.filter(db.or_(PoolItem.claimed_by == rater_id,
                            PoolItem.completed_by == rater_id))
    if since:
        q = q.filter(db.or_(PoolItem.claimed_at >= since, PoolItem.completed_at >= since))
    q = q.filter(db.or_(PoolItem.claimed_at.isnot(None), PoolItem.completed_at.isnot(None)))

    # Each row yields at most two events (pulled + finished), so 2x rows covers `limit` events.
    rows = q.order_by(db.func.coalesce(PoolItem.completed_at, PoolItem.claimed_at).desc()
                      ).limit(max(limit, 1) * 2).all()

    ids = {x for it in rows for x in (it.claimed_by, it.completed_by) if x}
    names = {r.id: r.name for r in Rater.query.filter(Rater.id.in_(ids)).all()} if ids else {}

    events = []
    for it in rows:
        base = {'item_id': it.id, 'task_id': it.task_id, 'language': it.language,
                'class': it.class_label, 'category': it.category,
                'task_type': task_type_label(it.task_type)}
        if it.completed_at:
            if it.is_flagged:
                event, detail = 'flagged', it.flag_reason or ''
            elif it.is_edited:
                event, detail = 'edited & labelled', f'difficulty {it.final_difficulty}'
            else:
                event, detail = 'labelled', f'difficulty {it.final_difficulty}'
            events.append(dict(base, when=it.completed_at, event=event, detail=detail,
                               annotator=names.get(it.completed_by, ''),
                               seconds=round((it.time_taken_ms or 0) / 1000.0, 1)))
        if it.claimed_at:
            events.append(dict(base, when=it.claimed_at, event='pulled', detail='',
                               annotator=names.get(it.claimed_by, ''), seconds=None))

    events.sort(key=lambda e: e['when'], reverse=True)
    return events[:limit]


@app.route('/api/pool/admin/activity', methods=['GET'])
@token_required
def pool_admin_activity(current_user):
    """What has happened in the pool recently -- the admin's audit feed.

    Filterable (event / annotator / language / free text) and paginated, so the
    feed stays usable however many pulls the pool accumulates.
    """
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    try:
        days = int(request.args.get('days') or 7)
    except (TypeError, ValueError):
        days = 7
    rater_id = request.args.get('rater_id', type=int)
    event = (request.args.get('event') or '').strip().lower()
    language = (request.args.get('language') or '').strip()
    search = (request.args.get('q') or '').strip().lower()
    try:
        page = max(int(request.args.get('page') or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = min(max(int(request.args.get('per_page') or 50), 10), 200)
    except (TypeError, ValueError):
        per_page = 50
    since = datetime.utcnow() - timedelta(days=max(days, 1)) if days else None

    events = _activity_events(team, since=since, rater_id=rater_id, limit=50000)

    # Counts per event type cover the whole window (before the event filter),
    # so the UI chips double as filter toggles without losing the totals.
    summary = {}
    for e in events:
        summary[e['event']] = summary.get(e['event'], 0) + 1

    if event:
        events = [e for e in events if e['event'] == event]
    if language:
        events = [e for e in events if (e['language'] or '') == language]
    if search:
        events = [e for e in events
                  if search in (f"{e['item_id']} {e.get('task_id') or ''} {e['annotator']} "
                                f"{e['detail']} {e['category'] or ''} {e['language'] or ''}").lower()]

    total = len(events)
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    start = (page - 1) * per_page
    events = events[start:start + per_page]

    return jsonify({
        'events': [dict(e, when=e['when'].isoformat(), when_ist=_ist_stamp(e['when']))
                   for e in events],
        'days': days,
        'count': total,
        'total': total,
        'page': page,
        'pages': pages,
        'per_page': per_page,
        'summary': summary,
    }), 200


@app.route('/api/pool/admin/export_activity_csv', methods=['GET'])
@token_required
def pool_export_activity_csv(current_user):
    """The same feed as a CSV, with full IST timestamps."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    try:
        days = int(request.args.get('days') or 30)
    except (TypeError, ValueError):
        days = 30
    since = datetime.utcnow() - timedelta(days=max(days, 1))
    events = _activity_events(team, since=since, limit=100000)

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Sr. No.', 'When (IST)', 'Event', 'Task type', 'Task ID', 'Item ID',
                'Language', 'Class', 'Category', 'Annotator', 'Detail', 'Seconds spent'])
    for i, e in enumerate(events, 1):
        w.writerow([i, _ist_stamp(e['when']), e['event'], e['task_type'],
                    e.get('task_id') or '', e['item_id'],
                    e['language'], e['class'], e['category'], e['annotator'],
                    e['detail'], e['seconds'] if e['seconds'] is not None else ''])

    stamp = datetime.utcnow().strftime('%Y%m%d')
    return csv_response(buf, f'asr_activity_{stamp}.csv')


# Per-annotator activity over a date window Mirrors /api/admin/rater_activity on the TTS side: the same date filter, the same headline strip, and a day-by-day.

def _parse_day(value):
    """'YYYY-MM-DD' (an IST calendar date) -> the UTC instant it starts at."""
    if not value:
        return None
    try:
        d = datetime.strptime(value.strip(), '%Y-%m-%d')
    except ValueError:
        return None
    return d - _IST                      # IST midnight expressed in UTC


def _rater_activity_payload(team, from_str, to_str):
    """What every annotator in this pool did between two IST days (both inclusive; either may be None for an open end)."""
    d_from = _parse_day(from_str)
    d_to = _parse_day(to_str)
    if d_to is not None:
        d_to = d_to + timedelta(days=1)          # inclusive end day

    members = TeamMember.query.filter_by(team_id=team.id).all()
    raters = {r.id: r for r in Rater.query.filter(
        Rater.id.in_([m.rater_id for m in members])).all()} if members else {}

    # Everything finished inside the window, one row per prompt.
    q = db.session.query(
        PoolItem.completed_by, PoolItem.completed_at, PoolItem.status,
        PoolItem.is_edited, PoolItem.final_difficulty, PoolItem.source_difficulty,
        PoolItem.language, PoolItem.time_taken_ms,
    ).filter(PoolItem.team_id == team.id, PoolItem.completed_by.isnot(None))
    if d_from is not None:
        q = q.filter(PoolItem.completed_at >= d_from)
    if d_to is not None:
        q = q.filter(PoolItem.completed_at < d_to)

    per_rater = {}
    totals = {'completed': 0, 'flagged': 0, 'edited': 0, 'difficulty_changed': 0,
              'seconds': 0.0, 'prompts': 0}
    for rid, when, status, edited, final_d, src_d, lang, ms in q.all():
        slot = per_rater.setdefault(rid, {
            'completed': 0, 'flagged': 0, 'edited': 0, 'difficulty_changed': 0,
            'seconds': 0.0, 'languages': {}, 'days': {}, 'last': None})
        day = _ist_day(when)
        d = slot['days'].setdefault(day, {'date': day, 'completed': 0, 'flagged': 0,
                                          'edited': 0, 'seconds': 0.0})
        if status == 'flagged':
            slot['flagged'] += 1
            d['flagged'] += 1
            totals['flagged'] += 1
        else:
            slot['completed'] += 1
            d['completed'] += 1
            totals['completed'] += 1
        if edited:
            slot['edited'] += 1
            d['edited'] += 1
            totals['edited'] += 1
        if final_d and src_d and final_d != src_d:
            slot['difficulty_changed'] += 1
            totals['difficulty_changed'] += 1
        secs = (ms or 0) / 1000.0
        slot['seconds'] += secs
        d['seconds'] += secs
        totals['seconds'] += secs
        totals['prompts'] += 1
        slot['languages'][lang] = slot['languages'].get(lang, 0) + 1
        if slot['last'] is None or when > slot['last']:
            slot['last'] = when

    holding = dict(db.session.query(PoolItem.claimed_by, func.count(PoolItem.id)).filter(
        PoolItem.team_id == team.id, PoolItem.status == 'claimed'
    ).group_by(PoolItem.claimed_by).all())

    rows = []
    for m in members:
        r = raters.get(m.rater_id)
        s = per_rater.get(m.rater_id)
        done = (s['completed'] + s['flagged']) if s else 0
        rows.append({
            'rater_id': m.rater_id,
            'name': r.name if r else f'#{m.rater_id}',
            'email': r.email if r else '',
            'is_active': bool(m.is_active) and bool(getattr(r, 'is_active', True)),
            'allowed_languages': [x.strip() for x in (m.languages or '').split(',') if x.strip()],
            'pull_size': m.pull_size,
            'completed': s['completed'] if s else 0,
            'flagged': s['flagged'] if s else 0,
            'edited': s['edited'] if s else 0,
            'difficulty_changed': s['difficulty_changed'] if s else 0,
            'done': done,
            'holding': holding.get(m.rater_id, 0),
            'hours': round((s['seconds'] if s else 0) / 3600.0, 2),
            'avg_seconds': round(s['seconds'] / done, 1) if (s and done) else 0.0,
            'languages': s['languages'] if s else {},
            'last_active': s['last'].isoformat() if (s and s['last']) else None,
            'last_active_ist': _ist_stamp(s['last']) if (s and s['last']) else '',
            'days': sorted(
                ({**d, 'seconds': round(d['seconds'], 1),
                  'hours': round(d['seconds'] / 3600.0, 2)} for d in s['days'].values()),
                key=lambda x: x['date'], reverse=True) if s else [],
        })
    rows.sort(key=lambda x: (-x['done'], x['name']))

    return {
        'from': from_str or None,
        'to': to_str or None,
        'today': _today_ist(),
        'totals': {
            'completed': totals['completed'],
            'flagged': totals['flagged'],
            'edited': totals['edited'],
            'difficulty_changed': totals['difficulty_changed'],
            'prompts': totals['prompts'],
            'hours': round(totals['seconds'] / 3600.0, 2),
            'active_annotators': sum(1 for r in rows if r['done'] > 0),
            'annotators': len(rows),
            'holding': sum(holding.values()),
        },
        'raters': rows,
    }


@app.route('/api/pool/admin/rater_activity', methods=['GET'])
@token_required
def pool_rater_activity(current_user):
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    return jsonify(_rater_activity_payload(team, request.args.get('from'),
                                           request.args.get('to'))), 200


@app.route('/api/pool/admin/export_rater_activity_csv', methods=['GET'])
@token_required
def pool_export_rater_activity_csv(current_user):
    """The same window, day by day, as a CSV."""
    team, err = _admin_pool_team(current_user)
    if err:
        return err
    payload = _rater_activity_payload(team, request.args.get('from'), request.args.get('to'))

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['Sr. No.', 'Annotator', 'Email', 'Date (IST)', 'Completed', 'Flagged',
                'Text edited', 'Hours', 'Task type'])
    n = 0
    for r in payload['raters']:
        for d in r['days']:
            n += 1
            w.writerow([n, r['name'], r['email'], d['date'], d['completed'], d['flagged'],
                        d['edited'], d['hours'], task_type_label('text-review')])
    stamp = datetime.utcnow().strftime('%Y%m%d')
    return csv_response(buf, f'asr_annotator_days_{stamp}.csv')
