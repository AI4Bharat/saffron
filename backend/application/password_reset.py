"""Password reset by one-time link.

There is no mail server, so a link cannot be sent to the annotator directly.
The flow instead goes through an admin, who already knows who their annotators
are:

  1. The annotator clicks "Forgot password?" and gives their username. This
     only files a request -- it never reveals whether the account exists, so
     the form cannot be used to discover usernames.
  2. An admin sees the request, and issues a link. The link is shown to the
     admin exactly once, to pass on over whatever channel they already use.
  3. The annotator opens the link and sets a new password.

What makes the link safe to send over chat:
  - the token is 32 random bytes, and only its SHA-256 is stored, so the
    database never holds anything that can be used to reset a password;
  - it expires (2 hours) and works once;
  - issuing or using a token cancels that annotator's other outstanding ones;
  - a wrong or stale token is refused without saying which of the two it was.

Passwords themselves are stored the way the rest of the app stores them, which
today is plain text -- this feature deliberately does not change that.
"""
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

from flask import jsonify, request

from main import app
from application.database import db
from application.models import Rater
from application.views import token_required, _is_admin, _admin_scope

TOKEN_TTL_HOURS = 2
MIN_PASSWORD_LEN = 6
# A username may only file this many requests in the window, so the queue
# cannot be flooded from the public form.
MAX_REQUESTS_PER_HOUR = 5


class PasswordReset(db.Model):
    """One reset request, and the token issued against it (if any)."""
    __tablename__ = 'password_reset'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False, index=True)
    # SHA-256 of the token. NULL until an admin issues one.
    token_hash = db.Column(db.String(64), nullable=True, index=True)
    status = db.Column(db.String(20), nullable=False, default='requested')
    # 'requested' -> 'issued' -> 'used'; or 'cancelled'
    requested_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    issued_at = db.Column(db.DateTime, nullable=True)
    issued_by = db.Column(db.String(100), nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    used_at = db.Column(db.DateTime, nullable=True)
    # Where the request came from, for the admin to sanity-check.
    source_ip = db.Column(db.String(64), nullable=True)

    def __repr__(self):
        return f"<PasswordReset rater={self.rater_id} status={self.status}>"


def _hash(token):
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _cancel_outstanding(rater_id):
    """Only one live token per annotator: issuing or using one voids the rest."""
    PasswordReset.query.filter(
        PasswordReset.rater_id == rater_id,
        PasswordReset.status.in_(['requested', 'issued']),
    ).update({'status': 'cancelled'}, synchronize_session=False)


def _client_ip():
    fwd = request.headers.get('X-Forwarded-For') or ''
    return (fwd.split(',')[0].strip() or request.remote_addr or '')[:64]


# annotator-facing

@app.route('/api/password_reset/request', methods=['POST'])
def password_reset_request():
    """File a reset request. Always answers the same way, whoever asks."""
    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    # One reply for every outcome: unknown user, rate-limited, or filed.
    same_answer = jsonify({
        'message': 'If that account exists, your admin has been notified. '
                   'They will send you a reset link.'
    }), 200
    if not username:
        return same_answer

    rater = Rater.query.filter_by(name=username).first()
    if rater is None:
        return same_answer

    since = datetime.utcnow() - timedelta(hours=1)
    recent = PasswordReset.query.filter(
        PasswordReset.rater_id == rater.id,
        PasswordReset.requested_at >= since).count()
    if recent >= MAX_REQUESTS_PER_HOUR:
        return same_answer

    try:
        db.session.add(PasswordReset(rater_id=rater.id, source_ip=_client_ip()))
        db.session.commit()
    except Exception:
        db.session.rollback()
    return same_answer


@app.route('/api/password_reset/check', methods=['GET'])
def password_reset_check():
    """Is this link still good? Used to show the form or an explanation."""
    token = (request.args.get('token') or '').strip()
    row = _live_row(token)
    if row is None:
        return jsonify({'valid': False,
                        'message': 'This reset link is invalid, already used, '
                                   'or has expired. Please ask your admin for a new one.'}), 200
    rater = Rater.query.get(row.rater_id)
    return jsonify({'valid': True, 'name': rater.name if rater else '',
                    'expires_at': row.expires_at.isoformat() if row.expires_at else None}), 200


def _live_row(token):
    """The usable row for this token, or None. Constant-time on the compare."""
    if not token or len(token) < 20:
        return None
    digest = _hash(token)
    row = PasswordReset.query.filter_by(token_hash=digest, status='issued').first()
    if row is None:
        return None
    if not hmac.compare_digest(row.token_hash or '', digest):
        return None
    if row.expires_at and row.expires_at < datetime.utcnow():
        return None
    return row


@app.route('/api/password_reset/complete', methods=['POST'])
def password_reset_complete():
    data = request.get_json() or {}
    token = (data.get('token') or '').strip()
    new_password = data.get('password') or ''

    if len(new_password) < MIN_PASSWORD_LEN:
        return jsonify({'message': f'Please choose a password of at least '
                                   f'{MIN_PASSWORD_LEN} characters.'}), 400

    row = _live_row(token)
    if row is None:
        return jsonify({'message': 'This reset link is invalid, already used, or has '
                                   'expired. Please ask your admin for a new one.'}), 400

    rater = Rater.query.get(row.rater_id)
    if rater is None:
        return jsonify({'message': 'That account no longer exists.'}), 400

    try:
        # Stored as the rest of the app stores it; changing that is a separate
        # decision and would break the existing login comparison.
        rater.password = new_password
        # Void the annotator's other links first: this row is still 'issued' at
        # that point, so it would otherwise be cancelled along with them.
        _cancel_outstanding(rater.id)
        row.status = 'used'
        row.used_at = datetime.utcnow()
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'Could not set the password. Please try again.'}), 500

    return jsonify({'message': 'Your password has been changed. You can sign in now.'}), 200


# admin-facing

def _admin_or_401(current_user):
    """Only the organisation admin may see or answer reset requests.

    Issuing a link is as good as handing over the account, so this is not
    delegated to team admins.
    """
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    scope, _team_id = _admin_scope(current_user)
    if scope != 'org':
        return jsonify({'message': 'Only the organisation admin can handle '
                                   'password resets.'}), 403
    return None


def _visible_rater_ids(current_user):
    """The org admin sees every annotator; nobody else reaches this code."""
    return None


@app.route('/api/admin/password_resets', methods=['GET'])
@token_required
def admin_password_resets(current_user):
    """Open requests, newest first."""
    err = _admin_or_401(current_user)
    if err:
        return err
    allowed = _visible_rater_ids(current_user)

    rows = PasswordReset.query.filter(
        PasswordReset.status.in_(['requested', 'issued'])
    ).order_by(PasswordReset.requested_at.desc()).limit(200).all()

    now = datetime.utcnow()
    out = []
    for r in rows:
        if allowed is not None and r.rater_id not in allowed:
            continue
        rater = Rater.query.get(r.rater_id)
        if rater is None:
            continue
        out.append({
            'id': r.id,
            'rater_id': r.rater_id,
            'name': rater.name,
            'email': rater.email or '',
            'status': r.status,
            'requested_at': r.requested_at.isoformat() if r.requested_at else None,
            'issued_at': r.issued_at.isoformat() if r.issued_at else None,
            'issued_by': r.issued_by or '',
            'expired': bool(r.expires_at and r.expires_at < now),
            'source_ip': r.source_ip or '',
        })
    return jsonify({'requests': out}), 200


def _issue_for(rater, current_user, existing=None):
    """Mint a token for this annotator and return the one-time link."""
    _cancel_outstanding(rater.id)
    token = secrets.token_urlsafe(32)
    row = existing if existing is not None else PasswordReset(rater_id=rater.id)
    row.rater_id = rater.id
    row.token_hash = _hash(token)
    row.status = 'issued'
    row.issued_at = datetime.utcnow()
    row.issued_by = current_user
    row.expires_at = datetime.utcnow() + timedelta(hours=TOKEN_TTL_HOURS)
    row.used_at = None
    if existing is None:
        db.session.add(row)
    db.session.commit()

    base = (request.headers.get('Origin')
            or request.host_url.rstrip('/'))
    return {
        'link': f"{base}/reset-password?token={token}",
        'expires_at': row.expires_at.isoformat(),
        'expires_in_hours': TOKEN_TTL_HOURS,
        'name': rater.name,
        'request_id': row.id,
    }


@app.route('/api/admin/password_resets/<int:req_id>/issue', methods=['POST'])
@token_required
def admin_password_reset_issue(current_user, req_id):
    """Issue a link against a request the annotator filed."""
    err = _admin_or_401(current_user)
    if err:
        return err
    row = PasswordReset.query.get(req_id)
    if row is None:
        return jsonify({'message': 'That request no longer exists.'}), 404
    allowed = _visible_rater_ids(current_user)
    if allowed is not None and row.rater_id not in allowed:
        return jsonify({'message': 'That annotator is not in your team.'}), 403
    rater = Rater.query.get(row.rater_id)
    if rater is None:
        return jsonify({'message': 'That account no longer exists.'}), 404
    try:
        return jsonify(_issue_for(rater, current_user, existing=row)), 200
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'Could not issue a link. Please try again.'}), 500


@app.route('/api/admin/password_resets/for_rater', methods=['POST'])
@token_required
def admin_password_reset_for_rater(current_user):
    """Issue a link for an annotator who could not file a request themselves."""
    err = _admin_or_401(current_user)
    if err:
        return err
    data = request.get_json() or {}
    rater_id = data.get('rater_id')
    rater = Rater.query.get(rater_id) if rater_id else None
    if rater is None:
        return jsonify({'message': 'Unknown annotator.'}), 404
    allowed = _visible_rater_ids(current_user)
    if allowed is not None and rater.id not in allowed:
        return jsonify({'message': 'That annotator is not in your team.'}), 403
    try:
        return jsonify(_issue_for(rater, current_user)), 200
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'Could not issue a link. Please try again.'}), 500


@app.route('/api/admin/password_resets/<int:req_id>/dismiss', methods=['POST'])
@token_required
def admin_password_reset_dismiss(current_user, req_id):
    err = _admin_or_401(current_user)
    if err:
        return err
    row = PasswordReset.query.get(req_id)
    if row is None:
        return jsonify({'message': 'That request no longer exists.'}), 404
    allowed = _visible_rater_ids(current_user)
    if allowed is not None and row.rater_id not in allowed:
        return jsonify({'message': 'That annotator is not in your team.'}), 403
    try:
        row.status = 'cancelled'
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({'message': 'Could not dismiss it. Please try again.'}), 500
    return jsonify({'message': 'Dismissed.'}), 200
