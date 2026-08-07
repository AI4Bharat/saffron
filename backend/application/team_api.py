"""Organisation / team administration API."""

from datetime import datetime

from flask import current_app as app, jsonify, request
from sqlalchemy import func
from werkzeug.security import generate_password_hash

from application.models import db, Rater, Team, TeamMember, AdminUser, Test, PoolItem
from application.views import (
    token_required, _is_admin, _admin_scope, _team_by_key, _serialize_team,
    _request_team_id, ORG_NAME,
)


def _require_org_admin(current_user):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    scope, _ = _admin_scope(current_user)
    if scope != 'org':
        return jsonify({'message': 'Only an organisation admin can do this.'}), 403
    return None


@app.route('/api/teams', methods=['GET'])
def list_teams_public():
    """Teams available at signup time."""
    teams = Team.query.filter_by(is_active=True).order_by(Team.id).all()
    return jsonify({'organization': ORG_NAME,
                    'teams': [{'key': t.key, 'name': t.name,
                               'description': t.description} for t in teams]}), 200


@app.route('/api/admin/teams', methods=['GET'])
@token_required
def admin_list_teams(current_user):
    """Teams the caller may administer, each with a headline count."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    scope, team_id = _admin_scope(current_user)
    q = Team.query.order_by(Team.id)
    if scope == 'team':
        q = q.filter(Team.id == team_id)

    member_counts = dict(db.session.query(TeamMember.team_id, func.count(TeamMember.id))
                         .filter(TeamMember.is_active == True)  # noqa: E712
                         .group_by(TeamMember.team_id).all())
    batch_counts = dict(db.session.query(Test.team_id, func.count(Test.id))
                        .group_by(Test.team_id).all())
    pool_counts = dict(db.session.query(PoolItem.team_id, func.count(PoolItem.id))
                       .group_by(PoolItem.team_id).all())

    out = []
    for t in q.all():
        d = _serialize_team(t)
        d['annotators'] = member_counts.get(t.id, 0)
        d['batches'] = batch_counts.get(t.id, 0)
        d['pool_items'] = pool_counts.get(t.id, 0)
        out.append(d)
    return jsonify({'organization': ORG_NAME, 'scope': scope, 'teams': out}), 200


@app.route('/api/admin/team', methods=['POST'])
@token_required
def admin_create_team(current_user):
    """Create another team under the organisation (org admin only)."""
    err = _require_org_admin(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    key = (data.get('key') or '').strip().lower()
    name = (data.get('name') or '').strip()
    if not key or not name:
        return jsonify({'message': 'A key and a name are required.'}), 400
    if not key.replace('-', '').replace('_', '').isalnum():
        return jsonify({'message': 'The key may only contain letters, digits, - and _.'}), 400
    if Team.query.filter_by(key=key).first():
        return jsonify({'message': f'A team with the key "{key}" already exists.'}), 409

    workflow = (data.get('workflow') or 'classic').strip().lower()
    if workflow not in ('classic', 'pool'):
        workflow = 'classic'
    team = Team(key=key, name=name, description=(data.get('description') or '').strip() or None,
                workflow=workflow, accent=(data.get('accent') or '#4f46e5'))
    db.session.add(team)
    db.session.commit()
    return jsonify({'message': f'{name} created.', 'team': _serialize_team(team)}), 201


@app.route('/api/admin/team/members', methods=['GET'])
@token_required
def admin_team_members(current_user):
    """Everyone in the team, plus everyone who could be added to it."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    team_id = _request_team_id(current_user)
    team = Team.query.get(team_id) if team_id else None
    if team is None:
        return jsonify({'message': 'Team not found'}), 404

    members = (TeamMember.query.filter_by(team_id=team.id)
               .join(Rater, Rater.id == TeamMember.rater_id)
               .order_by(Rater.name).all())
    member_ids = {m.rater_id for m in members if m.is_active}

    # Which other teams each of these annotators also works for.
    other = {}
    for m in TeamMember.query.filter(TeamMember.rater_id.in_(list(member_ids or [0])),
                                     TeamMember.is_active == True).all():  # noqa: E712
        if m.team_id != team.id:
            other.setdefault(m.rater_id, []).append(m.team_id)
    team_names = {t.id: t.name for t in Team.query.all()}

    out = []
    for m in members:
        r = m.rater
        out.append({
            'rater_id': m.rater_id,
            'name': r.name if r else f'#{m.rater_id}',
            'email': r.email if r else '',
            'role': m.role,
            'is_active': bool(m.is_active) and bool(getattr(r, 'is_active', True)),
            'languages': [x.strip() for x in (m.languages or '').split(',') if x.strip()],
            'pull_size': m.pull_size,
            'also_in': [team_names.get(tid, str(tid)) for tid in other.get(m.rater_id, [])],
            'joined': m.created_at.isoformat() if m.created_at else None,
        })

    candidates = [{'id': r.id, 'name': r.name, 'email': r.email}
                  for r in Rater.query.order_by(Rater.name).all()
                  if r.id not in member_ids]

    return jsonify({'team': _serialize_team(team), 'members': out,
                    'candidates': candidates}), 200


@app.route('/api/admin/team/member', methods=['POST'])
@token_required
def admin_team_member(current_user):
    """Add an annotator to this team, or deactivate their membership."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    team_id = _request_team_id(current_user)
    team = Team.query.get(team_id) if team_id else None
    if team is None:
        return jsonify({'message': 'Team not found'}), 404

    data = request.get_json(silent=True) or {}
    rater = Rater.query.get(data.get('rater_id')) if data.get('rater_id') else None
    if rater is None:
        return jsonify({'message': 'Annotator not found'}), 404

    m = TeamMember.query.filter_by(team_id=team.id, rater_id=rater.id).first()
    if data.get('remove'):
        if m is None or not m.is_active:
            return jsonify({'message': f'{rater.name} is not in {team.name}.'}), 200
        m.is_active = False
        released = 0
        if team.workflow == 'pool':
            for it in PoolItem.query.filter_by(team_id=team.id, claimed_by=rater.id,
                                               status='claimed').all():
                it.status, it.claimed_by, it.claimed_at, it.pull_id = 'available', None, None, None
                released += 1
        db.session.commit()
        msg = f'{rater.name} removed from {team.name}.'
        if released:
            msg += f' {released} unfinished item(s) returned to the pool.'
        return jsonify({'message': msg}), 200

    if m is None:
        m = TeamMember(team_id=team.id, rater_id=rater.id, role='annotator')
        db.session.add(m)
    m.is_active = True
    if 'languages' in data:
        langs = data.get('languages') or []
        if isinstance(langs, str):
            langs = langs.split(',')
        m.languages = ','.join(x.strip() for x in langs if x and x.strip())
    if data.get('pull_size'):
        try:
            m.pull_size = max(1, min(int(data['pull_size']), 500))
        except (TypeError, ValueError):
            pass
    db.session.commit()
    return jsonify({'message': f'{rater.name} added to {team.name}.'}), 200


# Admin accounts (org admin only)

@app.route('/api/admin/admins', methods=['GET'])
@token_required
def admin_list_admins(current_user):
    err = _require_org_admin(current_user)
    if err:
        return err
    rows = AdminUser.query.order_by(AdminUser.id).all()
    teams = {t.id: t for t in Team.query.all()}
    return jsonify({'admins': [{
        'id': a.id,
        'username': a.username,
        'display_name': a.display_name,
        'email': a.email,
        'scope': a.scope,
        'team': _serialize_team(teams[a.team_id]) if a.team_id in teams else None,
        'is_active': bool(a.is_active),
        'last_login': a.last_login.isoformat() if a.last_login else None,
    } for a in rows]}), 200


@app.route('/api/admin/admins', methods=['POST'])
@token_required
def admin_create_admin(current_user):
    """Create a team admin (or another org admin). Passwords are stored hashed."""
    err = _require_org_admin(current_user)
    if err:
        return err
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or len(password) < 6:
        return jsonify({'message': 'A username and a password of at least 6 characters are required.'}), 400
    if AdminUser.query.filter_by(username=username).first():
        return jsonify({'message': 'That admin username already exists.'}), 409
    if Rater.query.filter_by(name=username).first():
        return jsonify({'message': 'An annotator already uses that name.'}), 409

    team = _team_by_key(data.get('team')) if data.get('team') else None
    admin = AdminUser(username=username, password=generate_password_hash(password),
                      display_name=(data.get('display_name') or username).strip(),
                      email=(data.get('email') or '').strip() or None,
                      team_id=team.id if team else None)
    db.session.add(admin)
    db.session.commit()
    return jsonify({'message': f'Admin "{username}" created'
                               + (f' for {team.name}.' if team else ' (organisation scope).'),
                    'id': admin.id}), 201


@app.route('/api/admin/admins/<int:admin_id>', methods=['PUT'])
@token_required
def admin_update_admin(current_user, admin_id):
    """Rotate a password, rename, re-scope or disable an admin account."""
    err = _require_org_admin(current_user)
    if err:
        return err
    admin = AdminUser.query.get_or_404(admin_id)
    data = request.get_json(silent=True) or {}

    if data.get('password'):
        if len(data['password']) < 6:
            return jsonify({'message': 'Password must be at least 6 characters.'}), 400
        admin.password = generate_password_hash(data['password'])
    if 'display_name' in data:
        admin.display_name = (data.get('display_name') or '').strip() or admin.username
    if 'email' in data:
        admin.email = (data.get('email') or '').strip() or None
    if 'team' in data:
        team = _team_by_key(data.get('team')) if data.get('team') else None
        admin.team_id = team.id if team else None
    if 'is_active' in data:
        if admin.username == 'admin' and not data['is_active']:
            return jsonify({'message': 'The organisation admin cannot be disabled.'}), 400
        admin.is_active = bool(data['is_active'])
    db.session.commit()
    return jsonify({'message': f'Admin "{admin.username}" updated.'}), 200


@app.route('/api/admin/org/overview', methods=['GET'])
@token_required
def admin_org_overview(current_user):
    """One screen for the org admin: every team with its live headline numbers."""
    err = _require_org_admin(current_user)
    if err:
        return err

    teams = Team.query.order_by(Team.id).all()
    members = dict(db.session.query(TeamMember.team_id, func.count(TeamMember.id))
                   .filter(TeamMember.is_active == True)  # noqa: E712
                   .group_by(TeamMember.team_id).all())
    batches = dict(db.session.query(Test.team_id, func.count(Test.id))
                   .group_by(Test.team_id).all())

    pool_by_team = {}
    for tid, status, cnt in db.session.query(
            PoolItem.team_id, PoolItem.status, func.count(PoolItem.id)
    ).group_by(PoolItem.team_id, PoolItem.status).all():
        slot = pool_by_team.setdefault(tid, {'total': 0, 'available': 0, 'claimed': 0,
                                             'completed': 0, 'flagged': 0})
        slot['total'] += cnt
        if status in slot:
            slot[status] += cnt

    out = []
    for t in teams:
        d = _serialize_team(t)
        d['annotators'] = members.get(t.id, 0)
        d['batches'] = batches.get(t.id, 0)
        pool = pool_by_team.get(t.id)
        if pool:
            pool['done'] = pool['completed'] + pool['flagged']
            pool['progress'] = round(100.0 * pool['done'] / pool['total'], 1) if pool['total'] else 0.0
        d['pool'] = pool
        out.append(d)

    # People who work for more than one team.
    shared = db.session.query(TeamMember.rater_id, func.count(TeamMember.id)).filter(
        TeamMember.is_active == True).group_by(TeamMember.rater_id).having(  # noqa: E712
        func.count(TeamMember.id) > 1).all()

    return jsonify({
        'organization': ORG_NAME,
        'teams': out,
        'totals': {
            'teams': len(teams),
            'annotators': db.session.query(func.count(Rater.id)).scalar() or 0,
            'multi_team_annotators': len(shared),
            'admins': AdminUser.query.filter_by(is_active=True).count(),
        },
        'generated_at': datetime.utcnow().isoformat(),
    }), 200
