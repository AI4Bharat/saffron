from flask import jsonify, request
import os
from werkzeug.security import generate_password_hash
from flask import current_app as app
from application.models import (db, Rater, Test, Rating, Message,
                                Team, TeamMember, AdminUser, PoolItem, PoolUpload)
from datetime import datetime, timedelta
import jwt
import uuid
from functools import wraps
import random
import logging
from logging.handlers import RotatingFileHandler
from flask_caching import Cache

# Deliberately not seeded: a fixed seed gave every worker the same stream.
# random.seed() with no argument reseeds from OS entropy.
random.seed()

cache_config = {
    'CACHE_TYPE': 'filesystem',  # More persistent than SimpleCache
    'CACHE_DIR': '/tmp/flask-cache',  # Cache directory
    'CACHE_DEFAULT_TIMEOUT': 6000,  # 10 minutes default
    'CACHE_THRESHOLD': 1000,  # Maximum number of items
    'CACHE_KEY_PREFIX': 'tts_saffron_'  # Prefix to avoid collisions
}
cache = Cache(config=cache_config)
cache.init_app(app)

def get_screening_timer_key(rater_id, study_id):
    return f"screening_timer_{rater_id}_{study_id}"


# Duration of the audio_segmentation WAV files, cached per (path, mtime) so the headers are only read once per file per worker.
_WAV_DURATION_CACHE = {}


def _wav_duration_seconds(filepath):
    import os
    import wave
    try:
        mtime = os.path.getmtime(filepath)
    except OSError:
        return 0.0
    hit = _WAV_DURATION_CACHE.get(filepath)
    if hit and hit[0] == mtime:
        return hit[1]
    try:
        with wave.open(filepath, 'rb') as w:
            rate = w.getframerate()
            dur = w.getnframes() / float(rate) if rate else 0.0
    except Exception:
        dur = 0.0
    _WAV_DURATION_CACHE[filepath] = (mtime, dur)
    return dur


# Audio-segmentation "hours done" helpers Every annotator on this project works in India and reads "today" as an IST day, but time_of_submission is stored in UTC.
_IST_OFFSET = timedelta(hours=5, minutes=30)

# Hours are credited for CLIPS THE ANNOTATOR ACTUALLY REVIEWED. A skipped clip was handed back without a verdict, so it is counted and reported separately and.
_SEG_HOURS_STATUS = 'completed'


def _ist_date_str(dt):
    """UTC datetime -> 'YYYY-MM-DD' in IST, or None."""
    if not dt:
        return None
    return (dt + _IST_OFFSET).date().isoformat()


def _ist_today_str():
    return _ist_date_str(datetime.utcnow())


def _audio_root():
    import os as _os
    return _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        'audio_segmentation'
    )


def _seg_durations_for_test(test, audio_root=None):
    """{task_id (str): clip duration in seconds} for one audio-segmentation Test."""
    import os as _os
    audio_root = audio_root or _audio_root()
    out = {}
    for item in (test.json_entry if isinstance(test.json_entry, list) else []):
        task_id = str(item.get('id') or '')
        filename = item.get('audio_filename')
        if not task_id or not filename:
            continue
        out[task_id] = _wav_duration_seconds(_os.path.join(audio_root, filename))
    return out


def _hms(seconds):
    """3725.4 -> '1h 2m'. Short-form label used by every hours widget."""
    seconds = int(round(seconds or 0))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def _hours_bucket():
    return {'clips': 0, 'seconds': 0.0, 'skipped': 0}


def _bucket_summary(b):
    return {
        'clips': b['clips'],
        'skipped': b['skipped'],
        'seconds': round(b['seconds'], 1),
        'hours': round(b['seconds'] / 3600.0, 2),
        'label': _hms(b['seconds']),
    }


def _daily_series(daily_map, days=30, end_date=None):
    """Dense, newest-first list of the last `days` IST days from {date_str: bucket}."""
    end = end_date or (datetime.utcnow() + _IST_OFFSET).date()
    out = []
    for i in range(days):
        d = (end - timedelta(days=i)).isoformat()
        b = daily_map.get(d) or _hours_bucket()
        row = _bucket_summary(b)
        row['date'] = d
        out.append(row)
    return out


# Set up logging
if not app.debug:
    _log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'logs')
    os.makedirs(_log_dir, exist_ok=True)
    handler = RotatingFileHandler(os.path.join(_log_dir, 'error.log'),
                                  maxBytes=10000, backupCount=1)
    handler.setLevel(logging.ERROR)
    app.logger.addHandler(handler)


@app.errorhandler(Exception)
def unhandled_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        # Return the error as JSON (never Werkzeug's HTML page) so the SPA can always parse a `message`.
        payload = {
            'message': e.description or e.name,
            'error': e.name,
            'status': e.code,
        }
        return jsonify(payload), e.code
    # exc_info=True records the full traceback in error.log for real debugging, while the client only ever sees a generic message (no internals leaked).
    app.logger.error('Unhandled Exception: %s', e, exc_info=True)
    return jsonify({'message': 'Something went wrong on our end. Please try again.',
                    'error': 'Internal Server Error', 'status': 500}), 500


def _require_bearer_token():
    """Return the bearer token from the Authorization header, or abort(401) with a clear JSON message."""
    from flask import abort
    parts = (request.headers.get('Authorization') or '').split()
    if len(parts) == 2 and parts[0].lower() == 'bearer':
        return parts[1]
    if len(parts) == 1 and parts[0]:
        return parts[0]  # tolerate a bare token without the "Bearer " prefix
    abort(401, description='Authorization token is missing or malformed.')


def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        # Accept 'Bearer <token>' or a bare token; anything else is a clean 401, never a 500.
        parts = (request.headers.get('Authorization') or '').split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            token = parts[1]
        elif len(parts) == 1 and parts[0]:
            token = parts[0]
        else:
            return jsonify({'message': 'Authorization token is missing or malformed.'}), 401
        try:
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Your session has expired. Please sign in again.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token!'}), 401
        return f(current_user, *args, **kwargs)
    return decorated

def get_remaining_time(rater_id, study_id):
    timer_key = get_screening_timer_key(rater_id, study_id)
    try:
        start_time = cache.get(timer_key)
        if not start_time:
            return 480  # 8 minutes default
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        remaining = max(480 - int(elapsed), 0)
        
        # Refresh cache if still active
        if remaining > 0:
            cache.set(timer_key, start_time, timeout=6000)
            
        return remaining
    except Exception as e:
        app.logger.error(f"Cache error in get_remaining_time: {e}")
        return 480  # Fallback to default

@app.route('/api/')
def index():
    return "API is running"


@app.route('/api/audio/<path:filename>', methods=['GET'])
def serve_audio(filename):
    import os
    import re
    from flask import request, Response
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # Audio lives in more than one place now: audio_segmentation/ holds the recording
    # sets (paths like 'set3/x.wav'), aivanta_task/ the transcript-correction clips
    # (paths like 'aivanta_task/Hindi_E_Commerce/x.wav'). A path whose first segment
    # names an allowed root resolves against backend/; anything else keeps the old
    # meaning and resolves inside audio_segmentation/.
    AUDIO_ROOTS = ('audio_segmentation', 'aivanta_task', 'tasks')
    head = filename.split('/', 1)[0]
    root = base_dir if head in AUDIO_ROOTS else os.path.join(base_dir, 'audio_segmentation')
    filepath = os.path.normpath(os.path.join(root, filename))

    # '..' in the URL must not reach outside the root, and only audio is servable.
    if not filepath.startswith(os.path.join(root, '')) or not filepath.lower().endswith('.wav'):
        return "File not found", 404

    if not os.path.isfile(filepath):
        return "File not found", 404
        
    file_size = os.path.getsize(filepath)
    range_header = request.headers.get('Range', None)
    
    if not range_header:
        def stream_full():
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(81920)
                    if not chunk:
                        break
                    yield chunk
        rv = Response(stream_full(), 200, mimetype='audio/wav', direct_passthrough=True)
        rv.headers.add('Content-Length', str(file_size))
        rv.headers.add('Accept-Ranges', 'bytes')
        return rv

    match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return "Invalid Range", 400
        
    start = int(match.group(1))
    end = match.group(2)
    end = int(end) if end else file_size - 1
    
    if start >= file_size:
        return "Range Not Satisfiable", 416
        
    length = end - start + 1
    
    def stream_range(start_byte, length_bytes):
        with open(filepath, 'rb') as f:
            f.seek(start_byte)
            remaining = length_bytes
            while remaining > 0:
                chunk_size = min(81920, remaining)
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk
                
    rv = Response(stream_range(start, length), 206, mimetype='audio/wav', direct_passthrough=True)
    rv.headers.add('Content-Range', f'bytes {start}-{end}/{file_size}')
    rv.headers.add('Content-Length', str(length))
    rv.headers.add('Accept-Ranges', 'bytes')
    return rv


# CRUD Rater


def generate_token(username, kind='rater', team=None, scope=None,
                   view_only=False, task_types=None):
    """JWT for an annotator or an admin."""
    payload = {
        'username': username,
        'kind': kind,
        'team': team,
        'scope': scope,
        # Carried in the token so every worker enforces it without a DB lookup.
        'view_only': bool(view_only),
        'task_types': task_types or [],
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')


SAFE_METHODS = ('GET', 'HEAD', 'OPTIONS')
# A read-only login still has to be able to end its own session.
VIEW_ONLY_WRITE_ALLOWLIST = ('/api/login', '/api/logout')


@app.before_request
def _block_writes_for_view_only():
    """Refuse any state-changing request made with a read-only admin token.

    Applied to every request rather than to individual routes, so a route added
    later is covered without anyone having to remember it.
    """
    if request.method in SAFE_METHODS:
        return None
    path = request.path or ''
    if not path.startswith('/api/'):
        return None
    if path in VIEW_ONLY_WRITE_ALLOWLIST:
        return None

    parts = (request.headers.get('Authorization') or '').split()
    token = parts[1] if len(parts) == 2 and parts[0].lower() == 'bearer' else (
        parts[0] if len(parts) == 1 and parts[0] else '')
    if not token:
        return None                      # unauthenticated: the route decides
    try:
        data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        return None                      # a bad token is the route's problem
    if data.get('view_only'):
        return jsonify({'message': 'This account is read-only.'}), 403
    return None


def token_task_types():
    """Test types the caller may see; empty list means no restriction."""
    parts = (request.headers.get('Authorization') or '').split()
    token = parts[1] if len(parts) == 2 and parts[0].lower() == 'bearer' else (
        parts[0] if len(parts) == 1 and parts[0] else '')
    if not token:
        return []
    try:
        data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    except Exception:
        return []
    return list(data.get('task_types') or [])


# Bodhan.AI identity helpers Two kinds of login exist: * ANNOTATOR -- a Rater row; their workspaces are their TeamMember rows.

ORG_NAME = os.environ.get('ORG_NAME', 'Bodhan.AI')

# Languages recognised when inferring a batch's language from its description. Extendable through the environment without a code change; the dashboard also unions in every language already present in the data.
KNOWN_LANGUAGES = [l.strip().lower() for l in os.environ.get(
    'SAFFRON_LANGUAGES',
    'hindi,bengali,gujarati,kannada,malayalam,marathi,odia,tamil,telugu,urdu,english'
).split(',') if l.strip()]


def _infer_language(description, known=None):
    """The first known language named in a batch description, '' if none."""
    desc_lower = (description or '').lower()
    for l in known if known is not None else KNOWN_LANGUAGES:
        if l in desc_lower:
            return l.capitalize()
    return ''


def _admin_row(username):
    """The AdminUser row for this username, or None."""
    if not username:
        return None
    try:
        return AdminUser.query.filter_by(username=username, is_active=True).first()
    except Exception:
        return None


def _is_admin(username):
    """True for the org admin and for every active team admin."""
    return username == 'admin' or _admin_row(username) is not None


def _admin_scope(username):
    """(scope, team_id) for an admin login. ('org', None) sees everything."""
    if username == 'admin':
        row = _admin_row('admin')
        if row is None or row.team_id is None:
            return 'org', None
        return 'team', row.team_id
    row = _admin_row(username)
    if row is None:
        return None, None
    return ('org', None) if row.team_id is None else ('team', row.team_id)


def _team_by_key(key):
    if not key:
        return None
    return Team.query.filter_by(key=str(key).strip().lower()).first()


def _default_team_id():
    """The team an unscoped admin request falls back to: the first active team."""
    t = _team_by_key(os.environ.get('DEFAULT_TEAM_KEY', '')) or \
        Team.query.filter_by(is_active=True).order_by(Team.id).first()
    return t.id if t else None


def _request_team_id(username):
    """The team this admin request is about."""
    scope, team_id = _admin_scope(username)
    if scope == 'team':
        return team_id
    requested = request.args.get('team') or request.headers.get('X-Team')
    team = _team_by_key(requested)
    if team:
        return team.id
    return _default_team_id()


def _team_test_ids(team_id):
    """Ids of the batches owned by a team (None = every batch)."""
    if team_id is None:
        return None
    return {tid for (tid,) in db.session.query(Test.id).filter(Test.team_id == team_id).all()}


def _team_rater_ids(team_id):
    """Ids of the annotators who belong to a team (None = every annotator)."""
    if team_id is None:
        return None
    return {r for (r,) in db.session.query(TeamMember.rater_id)
            .filter(TeamMember.team_id == team_id).all()}


def _scoped_tests(team_id, query=None):
    q = query if query is not None else Test.query
    if team_id is None:
        return q
    return q.filter(Test.team_id == team_id)


def _scoped_raters(team_id, query=None):
    """The annotators of a team."""
    q = query if query is not None else Rater.query
    if team_id is None:
        return q
    return q.join(TeamMember, TeamMember.rater_id == Rater.id).filter(
        TeamMember.team_id == team_id, TeamMember.is_active == True)  # noqa: E712


def _rater_in_scope(username, rater):
    """Can this admin act on this annotator? An org admin can act on anyone; a team admin only on the members of their own team."""
    scope, team_id = _admin_scope(username)
    if scope != 'team' or team_id is None or rater is None:
        return True
    return TeamMember.query.filter_by(team_id=team_id, rater_id=rater.id).first() is not None


def _serialize_team(team):
    return {
        'id': team.id,
        'key': team.key,
        'name': team.name,
        'description': team.description,
        'workflow': team.workflow,
        'accent': team.accent,
        'settings': team.settings if isinstance(team.settings, dict) else {},
        'is_active': bool(team.is_active),
    }


def _rater_teams(rater):
    """Every active workspace this annotator can enter, in a stable order."""
    rows = (TeamMember.query.filter_by(rater_id=rater.id, is_active=True)
            .join(Team, Team.id == TeamMember.team_id)
            .filter(Team.is_active == True)  # noqa: E712
            .order_by(Team.id).all())
    out = []
    for m in rows:
        entry = _serialize_team(m.team)
        entry['role'] = m.role
        entry['languages'] = [x.strip() for x in (m.languages or '').split(',') if x.strip()]
        entry['pull_size'] = m.pull_size
        out.append(entry)
    return out


@app.route('/api/login', methods=['POST'])
def login():
    """Single entry point for annotators and admins."""
    import os
    from werkzeug.security import check_password_hash

    data = request.get_json() or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    # 1. Annotator login.
    user = Rater.query.filter_by(name=username).first()
    if user and user.password == password:
        # Deactivated annotators cannot log in (reversible via admin reactivate).
        if getattr(user, 'is_active', True) is False:
            return jsonify({'message': 'This account has been deactivated. Please contact the admin.'}), 403
        teams = _rater_teams(user)
        return jsonify({
            'token': generate_token(username, kind='rater'),
            'role': 'annotator',
            'name': user.name,
            'organization': ORG_NAME,
            'teams': teams,
        }), 200

    # 2. Admin login -- team admins live in admin_user, hashed.
    admin = AdminUser.query.filter_by(username=username).first()
    if admin is not None:
        if not admin.is_active:
            return jsonify({'message': 'This admin account has been disabled.'}), 403
        ok = False
        try:
            ok = check_password_hash(admin.password, password)
        except Exception:
            ok = False
        # The org admin's password may also be rotated through the environment without touching the DB -- keep honouring ADMIN_PASSWORD for it.
        if not ok and admin.username == 'admin':
            ok = password == os.getenv('ADMIN_PASSWORD', 'admin')
        if ok:
            admin.last_login = datetime.utcnow()
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
            team = admin.team
            view_only = bool(getattr(admin, 'is_view_only', False))
            task_types = list(getattr(admin, 'task_types', []) or [])
            return jsonify({
                'token': generate_token(admin.username, kind='admin',
                                        team=team.key if team else None,
                                        scope=admin.scope,
                                        view_only=view_only,
                                        task_types=task_types),
                'role': 'admin',
                'scope': admin.scope,
                'view_only': view_only,
                'task_types': task_types,
                'name': admin.display_name or admin.username,
                'organization': ORG_NAME,
                'team': _serialize_team(team) if team else None,
                'teams': [_serialize_team(t) for t in
                          Team.query.filter_by(is_active=True).order_by(Team.id).all()]
                         if admin.team_id is None else [_serialize_team(team)],
            }), 200
        return jsonify({'message': 'Invalid username or password'}), 401

    # 3. Fallback for the historical env-only admin (before admin_user is seeded).
    if username == 'admin' and password == os.getenv('ADMIN_PASSWORD', 'admin'):
        return jsonify({
            'token': generate_token('admin', kind='admin', scope='org'),
            'role': 'admin', 'scope': 'org', 'name': f'{ORG_NAME} Admin',
            'organization': ORG_NAME,
            'teams': [_serialize_team(t) for t in Team.query.order_by(Team.id).all()],
        }), 200

    return jsonify({'message': 'Invalid username or password'}), 401


@app.route('/api/health', methods=['GET'])
def health():
    """Liveness + DB reachability probe for monitors and load balancers."""
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({'status': 'ok', 'database': 'ok',
                        'time': datetime.utcnow().isoformat()}), 200
    except Exception as e:
        return jsonify({'status': 'degraded', 'database': 'unreachable',
                        'detail': str(e)}), 503


@app.route('/api/me', methods=['GET'])
@token_required
def whoami(current_user):
    """Identity + workspaces for the signed-in user."""
    if _is_admin(current_user):
        scope, team_id = _admin_scope(current_user)
        row = _admin_row(current_user)
        team = Team.query.get(team_id) if team_id else None
        return jsonify({
            'role': 'admin',
            'scope': scope or 'org',
            'username': current_user,
            'name': (row.display_name if row else None) or current_user,
            'organization': ORG_NAME,
            'team': _serialize_team(team) if team else None,
            'teams': [_serialize_team(t) for t in
                      Team.query.filter_by(is_active=True).order_by(Team.id).all()]
                     if team is None else [_serialize_team(team)],
        }), 200

    rater = Rater.query.filter_by(name=current_user).first()
    if not rater:
        return jsonify({'message': 'User not found'}), 404
    return jsonify({
        'role': 'annotator',
        'username': rater.name,
        'name': rater.name,
        'email': rater.email,
        'organization': ORG_NAME,
        'teams': _rater_teams(rater),
    }), 200


# Daily signup PIN New annotators must enter an 8-digit PIN that the admin shares.
import os  # noqa: E402  (views.py imports os further down; needed at module level here)

# Public base URL used to build deep links into a specific task (see TestView ?task=).
_SAFFRON_BASE_URL = os.environ.get('SAFFRON_BASE_URL', 'https://tts-saffron.ai4bharat.org')

SIGNUP_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'state', 'signup_key.txt'
)


def _daily_signup_pin():
    """Return today's 8-digit PIN, generating + persisting a new one if the stored PIN is from a previous day (or the file is missing/corrupt)."""
    import datetime as _dt
    import fcntl as _fcntl
    import secrets as _secrets

    today = _dt.date.today().isoformat()
    # 'a+' creates the file when missing and lets us read AND rewrite under one lock.
    with open(SIGNUP_KEY_FILE, 'a+', encoding='utf-8') as fh:
        _fcntl.flock(fh.fileno(), _fcntl.LOCK_EX)   # released on close, but be explicit
        try:
            fh.seek(0)
            parts = fh.read().split()
            if (len(parts) >= 2 and parts[0] == today
                    and len(parts[1]) == 8 and parts[1].isdigit()):
                return parts[1]
            pin = ''.join(str(_secrets.randbelow(10)) for _ in range(8))
            fh.seek(0)
            fh.truncate()
            fh.write(f"{today} {pin}\n")
            fh.flush()
            os.fsync(fh.fileno())
            return pin
        finally:
            _fcntl.flock(fh.fileno(), _fcntl.LOCK_UN)


@app.route('/api/admin/signup-key', methods=['GET'])
@token_required
def get_signup_key(current_user):
    """Admin-only: today's signup PIN, to share with people who should sign up."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import datetime as _dt
    return jsonify({'pin': _daily_signup_pin(), 'date': _dt.date.today().isoformat()}), 200


@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()

    # Require the admin's daily 8-digit signup PIN (blocks anonymous signups).
    submitted_pin = str(data.get('signup_key') or data.get('signup_pin') or '').strip()
    if not submitted_pin:
        return jsonify({'message': 'A signup PIN is required. Please ask the admin for today\'s PIN.'}), 403
    if submitted_pin != _daily_signup_pin():
        return jsonify({'message': 'Invalid or expired signup PIN. The PIN changes daily - please ask the admin for today\'s PIN.'}), 403

    # Extract data from the request
    name = data.get('name')
    age = data.get('age')
    gender = data.get('gender')
    email = data.get('email')
    password = data.get('password')

    if AdminUser.query.filter_by(username=(name or '').strip()).first():
        return jsonify({'message': 'That username is reserved.'}), 400

    # Check if the username or email already exists
    existing_user = Rater.query.filter_by(email=email).first()  # Check if email exists in the database
    if existing_user:
        print("here")
        return jsonify({'message': 'Email already exists'}), 400  # Return error if email exists
    
    existing_user = Rater.query.filter_by(name=name).first()  # Check if email exists in the database
    if existing_user:
        print("here")
        return jsonify({'message': 'Username already exists'}), 400  # Return error if email exists

    # Create a new Rater instance (new user)
    new_user = Rater(
        name=name.strip(),
        age=age,
        gender=gender.strip(),
        email=email.strip(),
        password=password.strip()
    )

    # A new account joins NO team: it waits in the approval queue until a team admin claims it into their team from the dashboard (Annotators -> Pending approval).
    try:
        db.session.add(new_user)
        db.session.commit()  # Commit to save the user in the database
    except Exception as e:
        db.session.rollback()  # In case of error, rollback the transaction
        return jsonify({'message': 'Error occurred while signing up. Please try again.',
                        'error': str(e)}), 500

    # Generate an authentication token for the new user
    auth_token = generate_token(name, kind='rater')

    # Return the token in the response
    return jsonify({'token': auth_token, 'role': 'annotator',
                    'organization': ORG_NAME,
                    'teams': _rater_teams(new_user)}), 201

# CRUD Tests via Login
@app.route('/api/test/<int:test_id>', methods=['GET'])
@token_required
def get_test(current_user, test_id):
    token = _require_bearer_token()
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    username = required["username"]
    rater = Rater.query.filter_by(name=username).first()
    if not rater:
        if _is_admin(username):
            rater = Rater.query.first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404
    rater_id = rater.id
    test = Test.query.filter_by(id=test_id).first_or_404()

    # Task assignment locking protection.
    my_assigned_ids = []
    if not _is_admin(username):
        my_assigned_ids = [int(x.strip()) for x in (rater.assigned_tasks or "").split(',') if x.strip().isdigit()]
        if test_id not in my_assigned_ids:
            other_raters = Rater.query.filter(
                Rater.id != rater.id,
                Rater.assigned_tasks.isnot(None),
                Rater.assigned_tasks != ""
            ).all()
            for other in other_raters:
                assigned_ids = [int(x.strip()) for x in other.assigned_tasks.split(',') if x.strip().isdigit()]
                if test_id in assigned_ids:
                    return jsonify({'message': 'This task is locked to another annotator.'}), 403

    # Get the page numbers and ratings that the rater has already done.
    if _is_admin(username):
        ratings = []
    else:
        ratings = Rating.query.filter_by(rater_id=rater_id, test_id=test_id).all()
    latest_status = {}
    for r in ratings:
        if r.page_no_progress:
            pid = str(r.page_no_progress)
            if pid not in latest_status or r.time_of_submission > latest_status[pid]['time']:
                latest_status[pid] = {
                    'status': r.completion_status or 'completed',
                    'time': r.time_of_submission
                }

    # Leftover reassignment / handoff (ADMIN-CONTROLLED via test.handoff_mode).
    others_completed_ids = set()
    if not _is_admin(username) and test_id in my_assigned_ids and bool(getattr(test, 'handoff_mode', False)):
        for r in Rating.query.filter(
            Rating.test_id == test_id,
            Rating.rater_id != rater_id,
            Rating.completion_status == 'completed'
        ).all():
            if r.page_no_progress:
                others_completed_ids.add(str(r.page_no_progress))

    # ALWAYS preserve the original json_entry order (no done-first shuffling) so the task list looks identical on every visit.
    ordered_samples = [s for s in test.json_entry if str(s['id']) not in others_completed_ids]

    # Map latest ratings by task ID to merge corrections
    latest_ratings = {}
    for r in ratings:
        if r.page_no_progress:
            pid = str(r.page_no_progress)
            if pid not in latest_ratings or r.time_of_submission > latest_ratings[pid].time_of_submission:
                latest_ratings[pid] = r

    # Inject completion_status and merge corrected translations into each entry
    required_response = []
    for sample in ordered_samples:
        sample_copy = {k: v for k, v in sample.items()}
        for k in ['dialogue', 'conversation', 'turns']:
            if k in sample_copy and isinstance(sample_copy[k], list):
                sample_copy[k] = [dict(turn) for turn in sample_copy[k]]
        # Benchmark verification merges the annotator's edits over raw_text / spoken_form below.
        if 'raw_text' in sample_copy:
            sample_copy['original_raw_text'] = sample_copy['raw_text']
        if 'spoken_form' in sample_copy:
            sample_copy['original_spoken_form'] = sample_copy['spoken_form']
        pid = str(sample_copy['id'])
        if pid in latest_ratings:
            rating = latest_ratings[pid]
            sample_copy['completion_status'] = rating.completion_status or 'completed'

            # Merge corrected translations and evaluation decisions from results_json
            rating_data = rating.results_json
            if isinstance(rating_data, dict):
                if 'pre_scene' in rating_data:
                    sample_copy['pre_scene'] = rating_data['pre_scene']
                if 'post_scene' in rating_data:
                    sample_copy['post_scene'] = rating_data['post_scene']
                # Sentence-correction tasks carry a single top-level corrected text.
                if 'text' in rating_data:
                    sample_copy['text'] = rating_data['text']
                # Merge conversation evaluation decisions
                if 'evaluation' in rating_data:
                    sample_copy['evaluation'] = rating_data['evaluation']
                if 'comments' in rating_data:
                    sample_copy['comments'] = rating_data['comments']
                if 'transcript' in rating_data:
                    sample_copy['transcript'] = rating_data['transcript']
                if 'rejection_reasons' in rating_data:
                    sample_copy['rejection_reasons'] = rating_data['rejection_reasons']
                if 'custom_rejection_reason' in rating_data:
                    sample_copy['custom_rejection_reason'] = rating_data['custom_rejection_reason']
                # Benchmark verification: reload the annotator's edited raw_text / spoken_form and their accept/reject decision so a saved draft or a completed item re-opens.
                if 'raw_text' in rating_data:
                    sample_copy['raw_text'] = rating_data['raw_text']
                if 'spoken_form' in rating_data:
                    sample_copy['spoken_form'] = rating_data['spoken_form']
                if 'decision' in rating_data:
                    sample_copy['decision'] = rating_data['decision']

                orig_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in sample_copy and isinstance(sample_copy[k], list)), None)
                rated_conv_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in rating_data and isinstance(rating_data[k], list)), None)
                
                if orig_conv_key and rated_conv_key:
                    orig_list = sample_copy[orig_conv_key]
                    rated_list = rating_data[rated_conv_key]
                    for i, orig_turn in enumerate(orig_list):
                        if i < len(rated_list):
                            rated_turn = rated_list[i]
                            for k, v in rated_turn.items():
                                if k not in ['role', 'english', 'english_text', 'original', 'original_text', 'en', 'text_en', 'speaker', 'user']:
                                    orig_turn[k] = v
        else:
            sample_copy['completion_status'] = 'uncompleted'
        required_response.append(sample_copy)

    # Resume at the first item THIS rater hasn't finished (in original order).
    page_no = next(
        (i for i, s in enumerate(required_response)
         if s.get('completion_status') not in ('completed', 'skipped')),
        len(required_response)
    )

    return jsonify({
        'test_id': test.id,
        'test_type': test.test_type,
        'description': test.description,
        'json_entry': required_response,
        'page_no': page_no
    })


@app.teardown_request
def _release_session(exc=None):
    # main.py keeps one app context pushed forever, so Flask-SQLAlchemy never
    # removes the scoped session between requests: without this, one Session and
    # one connection stay bound to the worker for its entire life. Ending the
    # session here does three things a bare rollback() did not:
    #
    #   1. Returns the connection to the pool instead of parking it "idle in
    #      transaction". Those parked transactions are what let a single
    #      ALTER TABLE queue behind them and stall every request (2026-08-18),
    #      and what made an idle-transaction timeout unsafe to enable.
    #   2. Discards a session whose connection died underneath it. A rollback()
    #      on a dead connection raises, leaving the session wedged, and the
    #      worker then answered PendingRollbackError for its next few hundred
    #      requests until --max-requests recycled it.
    #   3. Guarantees a failed view's half-written objects cannot survive into
    #      the NEXT request on this worker and be flushed by its commit().
    #
    # This cannot lose a submission: every route commits what it means to keep
    # before it returns (audited across views.py/pool_api.py/pool_common.py --
    # the only writer without its own commit is release_pull_items(), whose
    # caller commits immediately after). Anything still uncommitted at teardown
    # is by definition work a failed request abandoned.
    try:
        db.session.remove()
    except Exception:
        # Closing a dead connection can raise. Drop the thread's session anyway,
        # so the next request builds a fresh one instead of inheriting the damage.
        try:
            db.session.registry.clear()
        except Exception:
            pass


@app.route('/api/ratings', methods=['POST'])
@token_required
def create_rating(current_user):
    try:
        token = _require_bearer_token()
        required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        rater = Rater.query.filter_by(name=required["username"]).first()
        if not rater:
            if _is_admin(required["username"]):
                rater = Rater.query.first()
            if not rater:
                return jsonify({'message': 'Rater not found'}), 404
        data = request.get_json()

        # Task assignment locking protection (a rater may always submit to their own assigned task)
        username = required["username"]
        test_id = data.get('test_id')
        if test_id and not _is_admin(username):
            my_assigned_ids = [int(x.strip()) for x in (rater.assigned_tasks or "").split(',') if x.strip().isdigit()]
            if test_id not in my_assigned_ids:
                other_raters = Rater.query.filter(
                    Rater.id != rater.id,
                    Rater.assigned_tasks.isnot(None),
                    Rater.assigned_tasks != ""
                ).all()
                for other in other_raters:
                    assigned_ids = [int(x.strip()) for x in other.assigned_tasks.split(',') if x.strip().isdigit()]
                    if test_id in assigned_ids:
                        return jsonify({'message': 'This task is locked to another annotator.'}), 403

        if 'results_json' not in data or not isinstance(data['results_json'], dict):
            return jsonify({'message': 'Invalid results_json format'}), 400

        data['results_json']['test_id'] = data['test_id']
        data['results_json']['rater_email'] = rater.email
        data['results_json']['time'] = datetime.now().isoformat()
        data['results_json']['time_taken'] = data['time_taken_to_submit'] / 1000
        data['results_json']['data_id'] = data.get('pageNo_progress')
        completion_status = data.get('completion_status', 'completed')
        # Denormalise the accept/reject verdict so no dashboard ever has to re-parse this blob to find it (see Rating.verdict).
        _v = data['results_json'].get('evaluation') or data['results_json'].get('decision')
        verdict = str(_v).strip().lower() if _v else ''

        existing_rating = Rating.query.filter_by(
            rater_id=rater.id,
            test_id=data['test_id'],
            page_no_progress=data.get('pageNo_progress')
        ).first()

        if existing_rating:
            existing_rating.results_json = data['results_json']
            existing_rating.time_taken_to_submit = data['time_taken_to_submit']
            existing_rating.completion_status = completion_status
            existing_rating.verdict = verdict
            existing_rating.time_of_submission = datetime.utcnow()
            db.session.commit()
            return jsonify({'message': 'Rating updated successfully'}), 200
        else:
            rating = Rating(
                rater_id=rater.id,
                test_id=data['test_id'],
                results_json=data['results_json'],
                time_taken_to_submit=data['time_taken_to_submit'],
                page_no_progress=data.get('pageNo_progress'),
                completion_status=completion_status,
                verdict=verdict,
            )
            db.session.add(rating)
            db.session.commit()
            return jsonify({'message': 'Rating created successfully'}), 201
    except Exception as e:
        # Roll back so a failed flush cannot poison this worker's session.
        db.session.rollback()
        app.logger.error('Error creating rating: %s', e)
        return jsonify({'message': 'Internal Server Error'}), 500


@app.route('/api/ratings/<int:rating_id>', methods=['PUT'])
@token_required
def update_rating(current_user, rating_id):
    # This endpoint used to be completely unauthenticated: anyone who could reach the API could overwrite any annotator's submission by id.
    rater = Rater.query.filter_by(name=current_user).first()
    rating = Rating.query.get_or_404(rating_id)
    if not _is_admin(current_user) and (not rater or rating.rater_id != rater.id):
        return jsonify({'message': 'Unauthorized'}), 403
    data = request.get_json() or {}
    if 'results_json' in data:
        rating.results_json = data['results_json']
        _v = (data['results_json'] or {}).get('evaluation') or (data['results_json'] or {}).get('decision')
        rating.verdict = str(_v).strip().lower() if _v else ''
    if 'time_taken_to_submit' in data:
        rating.time_taken_to_submit = data['time_taken_to_submit']
    if 'page_no_progress' in data:
        rating.page_no_progress = data['page_no_progress']
    db.session.commit()
    return jsonify({'message': 'Rating updated successfully'})


# Prolific recruitment flow (RETIRED 2026-08-06) The /api/prolific/* endpoints, the Study/Session/Consent models and their three (empty) tables were removed when.

# CRUD Basic
@app.route('/api/test', methods=['POST'])
@token_required
def create_test(current_user):
    """Create a new test. Sign-in required, as for every other write."""
    try:
        data = request.get_json()

        # Extract the required fields
        test_type = data.get('test_type')
        description = data.get('description')
        json_entry = data.get('json_entry')

        # Validate input
        if not test_type or not json_entry:
            return jsonify({'message': 'Missing required fields: test_type or json_entry'}), 400

        if not isinstance(json_entry, list):
            return jsonify({'message': 'Invalid json_entry format. Expected a list of JSON objects.'}), 400

        # Create a new Test instance
        new_test = Test(
            test_type=test_type,
            description=description,
            json_entry=json_entry
        )

        # Add the test to the database
        db.session.add(new_test)
        db.session.commit()

        return jsonify({'message': 'Test created successfully', 'test_id': new_test.id}), 201

    except Exception as e:
        app.logger.error('Error creating test: %s', e)
        db.session.rollback()
        return jsonify({'message': 'Error creating test'}), 500


@app.route('/api/results', methods=['GET'])
def get_database():
    """Get the contents of the database."""
    # Verify token
    token = _require_bearer_token()
    if token != "tts_ai4b":
        return jsonify({'message': 'Unauthorized'}), 401
    ratings = Rating.query.all()
    results = []
    for rating in ratings:
        results.append({
            'id': rating.id,
            'rater_id': rating.rater_id,
            'test_id': rating.test_id,
            'results_json': rating.results_json,
            'time_taken_to_submit': rating.time_taken_to_submit,
            'page_no_progress': rating.page_no_progress,
            'completion_status': rating.completion_status or 'completed'
        })
    return jsonify(results)

@app.route('/api/results/<int:test_id>', methods=['GET'])
def get_database_test(test_id):
    # check token
    token = _require_bearer_token()
    if token != "tts_ai4b":
        return jsonify({'message': 'Unauthorized'}), 401
    rating = Rating.query.filter_by(test_id=test_id).all()
    results = []
    for rate in rating:
        results.append({
            'id': rate.id,
            'rater_id': rate.rater_id,
            'test_id': rate.test_id,
            'results_json': rate.results_json,
            'time_taken_to_submit': rate.time_taken_to_submit,
            'page_no_progress': rate.page_no_progress,
            'completion_status': rate.completion_status or 'completed'
        })
    return jsonify(results)


@app.route('/api/verify_test/<int:test_id>', methods=['GET'])
def verify_test(test_id):
    token = _require_bearer_token()
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    
    username = required["username"]
    rater = Rater.query.filter_by(name=username).first()
    if not rater:
        if _is_admin(username):
            rater = Rater.query.first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404
    
    test = Test.query.filter_by(id=test_id).first_or_404()

    # Task assignment locking protection (a rater may always access their own assigned task)
    if not _is_admin(username):
        my_assigned_ids = [int(x.strip()) for x in (rater.assigned_tasks or "").split(',') if x.strip().isdigit()]
        if test_id not in my_assigned_ids:
            other_raters = Rater.query.filter(
                Rater.id != rater.id,
                Rater.assigned_tasks.isnot(None),
                Rater.assigned_tasks != ""
            ).all()
            for other in other_raters:
                assigned_ids = [int(x.strip()) for x in other.assigned_tasks.split(',') if x.strip().isdigit()]
                if test_id in assigned_ids:
                    return jsonify({'message': 'This task is locked to another annotator.'}), 403

    if not test:
        return jsonify({'message': 'Test not found'}), 404

    ratings = Rating.query.filter_by(
                rater_id=rater.id, test_id=test.id
            ).all()
    completed_pages_raw = {rating.page_no_progress for rating in ratings if rating.page_no_progress and rating.completion_status in ['completed', 'skipped']}

    # Get all pages in the test
    all_pages = [entry['id'] for entry in test.json_entry]

    # Filter out completed pages and shuffle the remaining ones
    completed_pages = {page for page in all_pages if str(page) in completed_pages_raw}
    remaining_pages = [page for page in all_pages if page not in completed_pages]

    if len(remaining_pages) == 0:
        return jsonify({'message': 'Test completed'}), 200
    else:
        return jsonify({'message': 'Test not completed'}), 404
    
@app.route('/api/tracking', methods=['GET'])
def get_tracking():
    token = _require_bearer_token()
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])

    if not token or not _is_admin(required["username"]):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        raters = Rater.query.all()
        tracking_data = []
        for rater in raters:
            if rater.gender.lower() == "unknown":
                continue
            # Get all ratings for the rater grouped by test.
            ratings = Rating.query.filter_by(rater_id=rater.id).all()
            test_groups = {}
            for rating in ratings:
                test_id = rating.test_id
                test_groups.setdefault(test_id, set())
                if rating.page_no_progress is not None:
                    test_groups[test_id].add(rating.page_no_progress)

            for test_id, completed in test_groups.items():
                test = Test.query.get(test_id)
                # Ratings can outlive their Test (e.g.
                if test is None:
                    continue
                total = len(test.json_entry) if test.json_entry else 0
                tracking_data.append({
                    'email': rater.email,
                    'test_id': test.id,
                    'test_type': test.test_type,
                    'test_desc': test.description,
                    'completed_pages': len(completed),
                    'total_pages': total
                })

        tracking_data.sort(key=lambda x: x['test_id'], reverse=True)
        return jsonify(tracking_data)
    except Exception as e:
        app.logger.error(f"Error in tracking endpoint: {e}")
        return jsonify({'error': 'Failed to fetch tracking data.'}), 500


@app.route('/api/admin/export_csv/<int:test_id>', methods=['GET'])
@token_required
def export_csv(current_user, test_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        from application.models import Rating, Test, Rater
        from flask import make_response
        import io
        import csv

        test = Test.query.get(test_id)
        if not test:
            return jsonify({'message': 'Test not found'}), 404
            
        from flask import request
        rater_id = request.args.get('rater_id', type=int)
        
        ratings_query = Rating.query.filter_by(test_id=test_id)
        if rater_id:
            ratings_query = ratings_query.filter_by(rater_id=rater_id)
        ratings = ratings_query.all()
        
        # Pre-fetch all raters once to avoid N+1 queries
        raters_map = {rater.id: rater for rater in Rater.query.all()}
        
        # Map original items by their ID
        original_items_map = {}
        if isinstance(test.json_entry, list):
            for item in test.json_entry:
                if isinstance(item, dict) and 'id' in item:
                    original_items_map[str(item['id'])] = item
                    
        # Base metadata headers common to all exports
        headers = [
            'Test ID',
            'Test Type',
            'Rater ID',
            'Rater Name',
            'Rater Email',
            'Item ID',
            'Listen (Saffron link)',
            'Completion Status',
            'Time of Submission',
            'Time Taken (seconds)'
        ]
        
        # Add task-type specific headers
        if test.test_type == 'sentence-correction':
            headers += [
                'Original English Text',
                'Original Translated Text',
                'Corrected Text',
                'Subject',
                'Level',
                'Language'
            ]
        elif test.test_type == 'transcript-correction':
            headers += [
                'Audio File',
                'Clip Title',
                'Domain',
                'Original Transcript',
                'Corrected Transcript',
                'Lines Changed',
                'Total Lines'
            ]
        elif test.test_type == 'conversation-evaluation':
            headers += [
                'Dialogue (Readable)',
                'Evaluation Decision',
                'Comments'
            ]
        elif test.test_type == 'audio-segmentation':
            headers += [
                'Speaker',
                'Role',
                'Language',
                'Persona',
                'Audio Filename',
                'Original Transcript',
                'Corrected Transcript',
                'Evaluation Decision',
                'Rejection Reasons',
                'Custom Rejection Reason',
                'Comments'
            ]
        elif test.test_type in ('benchmark-verification', 'benchmark-parallel', 'benchmark-evaluation-v2'):
            headers += [
                'Language',
                'Suite',
                'Domain',
                'Phenomenon Tags',
                'Probes Axes',
                'Quota Class',
                'Length Bucket',
                'Target Emotion',
                'Source ID',
                'English Raw Text',
                'English Spoken Form',
                'Original Raw Text',
                'Corrected Raw Text',
                'Raw Text Changed',
                'Original Spoken Form',
                'Corrected Spoken Form',
                'Spoken Form Changed',
                'Decision',
                'Comments'
            ]
        elif test.test_type == 'translation-correction':
            headers += [
                'Original Pre-scene',
                'Corrected Pre-scene',
                'Original Post-scene',
                'Corrected Post-scene',
                'Dialogue Annotations (Readable)'
            ]
        else:
            headers += [
                'Original Text',
                'Corrected Text',
                'Original Pre-scene',
                'Corrected Pre-scene',
                'Original Post-scene',
                'Corrected Post-scene',
                'Evaluation Decision',
                'Comments',
                'Dialogue Annotations (Readable)'
            ]
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(headers)
        
        for r in ratings:
            rater = raters_map.get(r.rater_id)
            res_json = r.results_json if isinstance(r.results_json, dict) else {}
            
            item_id = r.page_no_progress or res_json.get('data_id') or res_json.get('id')
            item_id_str = str(item_id) if item_id is not None else ""
            orig_item = original_items_map.get(item_id_str, {})
            
            # Base metadata row values
            row = [
                test.id,
                test.test_type,
                r.rater_id,
                rater.name if rater else "",
                rater.email if rater else "",
                item_id_str,
                (f"{_SAFFRON_BASE_URL}/{test.id}?task={item_id_str}" if item_id_str else ""),
                r.completion_status or 'completed',
                r.time_of_submission.isoformat() if r.time_of_submission else "",
                # Stored in MILLISECONDS (every frontend sends a Date.now() delta).
                round((r.time_taken_to_submit or 0.0) / 1000.0, 1)
            ]
            
            if test.test_type == 'sentence-correction':
                # Original English
                orig_en = orig_item.get('text_en') or orig_item.get('english') or orig_item.get('original') or ""
                # Original translation in config
                orig_trans = orig_item.get('text') or orig_item.get('translation') or ""
                # Corrected translation from rating
                corr_text = res_json.get('text') or ""
                
                row += [
                    orig_en,
                    orig_trans,
                    corr_text,
                    orig_item.get('subject') or res_json.get('subject') or "",
                    orig_item.get('level') or res_json.get('level') or "",
                    orig_item.get('target_language') or res_json.get('target_language') or ""
                ]
            elif test.test_type == 'transcript-correction':
                row += [
                    orig_item.get('audio_filename') or '',
                    orig_item.get('title') or '',
                    orig_item.get('domain') or '',
                    res_json.get('original_text') or orig_item.get('text') or '',
                    res_json.get('text') or '',
                    res_json.get('lines_changed', ''),
                    res_json.get('n_lines', orig_item.get('n_lines', '')),
                ]
            elif test.test_type == 'conversation-evaluation':
                # Build readable dialogue turns for context
                dialogue_turns_list = []
                orig_dialogue_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in orig_item and isinstance(orig_item[k], list)), None)
                if orig_dialogue_key:
                    for idx, orig_turn in enumerate(orig_item[orig_dialogue_key]):
                        speaker = orig_turn.get('speaker') or orig_turn.get('role') or f"Speaker {idx+1}"
                        turn_text = orig_turn.get('text') or orig_turn.get('english') or orig_turn.get('original') or ""
                        dialogue_turns_list.append(f"Turn {idx+1} [{speaker}]: {turn_text}")
                dialogue_readable = "\n".join(dialogue_turns_list)
                
                row += [
                    dialogue_readable,
                    res_json.get('evaluation', ''),
                    res_json.get('comments', '')
                ]
            elif test.test_type == 'audio-segmentation':
                rejection_reasons_str = ""
                if isinstance(res_json.get('rejection_reasons'), list):
                    rejection_reasons_str = ", ".join(res_json.get('rejection_reasons'))
                row += [
                    orig_item.get('speaker') or "",
                    orig_item.get('role') or "",
                    orig_item.get('language') or "",
                    orig_item.get('persona') or "",
                    orig_item.get('audio_filename') or "",
                    orig_item.get('transcript') or "",
                    res_json.get('transcript') or "",
                    res_json.get('evaluation') or "",
                    rejection_reasons_str,
                    res_json.get('custom_rejection_reason') or "",
                    res_json.get('comments') or ""
                ]
            elif test.test_type in ('benchmark-verification', 'benchmark-parallel', 'benchmark-evaluation-v2'):
                # The stored item is the pristine source row; the rating carries the annotator's edit.
                orig_raw = orig_item.get('raw_text') or ""
                orig_spoken = orig_item.get('spoken_form') or ""
                corr_raw = res_json.get('raw_text', orig_raw)
                corr_spoken = res_json.get('spoken_form', orig_spoken)
                tags = orig_item.get('phenomenon_tags')
                axes = orig_item.get('probes_axes')
                row += [
                    orig_item.get('lang') or orig_item.get('language') or "",
                    orig_item.get('suite') or "",
                    orig_item.get('domain') or "",
                    ", ".join(tags) if isinstance(tags, list) else (tags or ""),
                    ", ".join(axes) if isinstance(axes, list) else (axes or ""),
                    orig_item.get('quota_class') or "",
                    orig_item.get('length_bucket') or "",
                    orig_item.get('target_emotion') or "",
                    orig_item.get('source_id') or "",
                    orig_item.get('_ref_source_raw_text') or "",
                    orig_item.get('_ref_source_spoken_form') or "",
                    orig_raw,
                    corr_raw,
                    "YES" if corr_raw != orig_raw else "no",
                    orig_spoken,
                    corr_spoken,
                    "YES" if corr_spoken != orig_spoken else "no",
                    res_json.get('decision') or "",
                    res_json.get('comments') or res_json.get('comment') or ""
                ]
            elif test.test_type == 'translation-correction':
                orig_pre = orig_item.get('pre_scene_en') or orig_item.get('pre_scene') or ""
                annotated_pre = res_json.get('pre_scene') or ""
                orig_post = orig_item.get('post_scene_en') or orig_item.get('post_scene') or ""
                annotated_post = res_json.get('post_scene') or ""
                
                # Dialogue formatting
                dialogue_turns_list = []
                orig_dialogue_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in orig_item and isinstance(orig_item[k], list)), None)
                rated_dialogue_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in res_json and isinstance(res_json[k], list)), None)
                
                if orig_dialogue_key and rated_dialogue_key:
                    orig_turns = orig_item[orig_dialogue_key]
                    rated_turns = res_json[rated_dialogue_key]
                    for idx, orig_turn in enumerate(orig_turns):
                        speaker = orig_turn.get('speaker') or orig_turn.get('role') or f"Speaker {idx+1}"
                        turn_orig = orig_turn.get('text') or orig_turn.get('english') or orig_turn.get('original') or ""
                        turn_rated = ""
                        if idx < len(rated_turns):
                            rated_turn = rated_turns[idx]
                            trans_key = next((k for k in ['translated', 'translation', 'translated_text', 'translated_sentence', 'text_translated', 'target', 'target_text', 'text'] if k in rated_turn), None)
                            if trans_key:
                                turn_rated = rated_turn[trans_key]
                        dialogue_turns_list.append(f"Turn {idx+1} [{speaker}]:\n  Original: {turn_orig}\n  Corrected: {turn_rated}")
                elif orig_dialogue_key:
                    for idx, orig_turn in enumerate(orig_item[orig_dialogue_key]):
                        speaker = orig_turn.get('speaker') or orig_turn.get('role') or f"Speaker {idx+1}"
                        turn_orig = orig_turn.get('text') or orig_turn.get('english') or orig_turn.get('original') or ""
                        dialogue_turns_list.append(f"Turn {idx+1} [{speaker}]:\n  Original: {turn_orig}")
                        
                dialogue_readable = "\n\n".join(dialogue_turns_list)
                
                row += [
                    orig_pre,
                    annotated_pre,
                    orig_post,
                    annotated_post,
                    dialogue_readable
                ]
            else:
                orig_text = orig_item.get('english') or orig_item.get('original') or orig_item.get('text_en') or orig_item.get('text') or ""
                annotated_text = res_json.get('text') or ""
                orig_pre = orig_item.get('pre_scene_en') or orig_item.get('pre_scene') or ""
                annotated_pre = res_json.get('pre_scene') or ""
                orig_post = orig_item.get('post_scene_en') or orig_item.get('post_scene') or ""
                annotated_post = res_json.get('post_scene') or ""
                
                dialogue_turns_list = []
                orig_dialogue_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in orig_item and isinstance(orig_item[k], list)), None)
                rated_dialogue_key = next((k for k in ['dialogue', 'conversation', 'turns'] if k in res_json and isinstance(res_json[k], list)), None)
                if orig_dialogue_key and rated_dialogue_key:
                    orig_turns = orig_item[orig_dialogue_key]
                    rated_turns = res_json[rated_dialogue_key]
                    for idx, orig_turn in enumerate(orig_turns):
                        speaker = orig_turn.get('speaker') or orig_turn.get('role') or f"Speaker {idx+1}"
                        turn_orig = orig_turn.get('text') or orig_turn.get('english') or orig_turn.get('original') or ""
                        turn_rated = ""
                        if idx < len(rated_turns):
                            rated_turn = rated_turns[idx]
                            trans_key = next((k for k in ['translated', 'translation', 'translated_text', 'translated_sentence', 'text_translated', 'target', 'target_text', 'text'] if k in rated_turn), None)
                            if trans_key:
                                turn_rated = rated_turn[trans_key]
                        dialogue_turns_list.append(f"Turn {idx+1} [{speaker}]:\n  Original: {turn_orig}\n  Corrected: {turn_rated}")
                dialogue_readable = "\n\n".join(dialogue_turns_list)
                
                row += [
                    orig_text,
                    annotated_text,
                    orig_pre,
                    annotated_pre,
                    orig_post,
                    annotated_post,
                    res_json.get('evaluation', ''),
                    res_json.get('comments', ''),
                    dialogue_readable
                ]
            writer.writerow(row)
            
        filename = f"annotations_task_{test_id}"
        if rater_id and ratings:
            rater_obj = raters_map.get(rater_id)
            if rater_obj:
                filename += f"_rater_{rater_obj.name.replace(' ', '_')}"
        filename += ".csv"
        
        response = make_response("\ufeff" + output.getvalue())
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        response.headers["Content-type"] = "text/csv; charset=utf-8"
        return response
    except Exception as e:
        app.logger.error(f"Error in export_csv endpoint: {e}")
        return jsonify({'error': 'Failed to export CSV.'}), 500


def _artist_stats_safe(tests, ratings_by_test):
    """Per-voice-artist rejection rollup; never break the dashboard if it fails."""
    try:
        import admin_reports
        return admin_reports.artist_rejection_stats(tests, ratings_by_test)
    except Exception as e:
        print(f"[WARN] artist stats failed: {e}")
        return {'artists': [], 'overall': {}, 'languages': [], 'all_languages': []}


@app.route('/api/admin/rater_activity', methods=['GET'])
@token_required
def rater_activity(current_user):
    """Per-annotator work done inside a date window (default: all time)."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from sqlalchemy.orm import defer
    from datetime import datetime as _dt, timedelta as _td

    def _parse(v):
        try:
            return _dt.strptime(v.strip(), '%Y-%m-%d')
        except Exception:
            return None

    d_from = _parse(request.args.get('from') or '')
    d_to = _parse(request.args.get('to') or '')

    import admin_reports

    q = Rating.query.options(defer(Rating.results_json))
    if d_from:
        q = q.filter(Rating.time_of_submission >= d_from)
    if d_to:
        q = q.filter(Rating.time_of_submission < d_to + _td(days=1))   # inclusive end day
    ratings = q.all()

    # test_id -> (test_type, description), so every submission can be attributed to a task type AND to the specific batch it came from.
    meta_of_test = {tid: (tt, desc)
                    for tid, tt, desc in db.session.query(Test.id, Test.test_type, Test.description).all()}

    per = {}
    for r in ratings:
        p = per.setdefault(r.rater_id, {'tasks': set(), 'skipped': set(), 'drafts': 0,
                                        'by_type': {}, 'type_subs': {}, 'type_skipped': {},
                                        'type_drafts': {}, 'by_test': {}, 'submissions': 0,
                                        'secs': 0.0, 'last': None,
                                        # QC verdicts (audio-segmentation), unique per item
                                        'accepted': set(), 'rejected': set(),
                                        'type_accepted': {}, 'type_rejected': {}})
        ttype = (meta_of_test.get(r.test_id) or (None, None))[0] or 'unknown'
        p['submissions'] += 1
        p['type_subs'][ttype] = p['type_subs'].get(ttype, 0) + 1
        bt = p['by_test'].setdefault(r.test_id, {'tasks': set(), 'skipped': set(), 'drafts': 0,
                                                 'subs': 0, 'secs': 0.0, 'last': None,
                                                 'accepted': set(), 'rejected': set()})
        bt['subs'] += 1
        # Key on (test_id, item) — item ids restart at 1 in every batch, so a bare item id collapses genuinely different tasks into one.
        key = (r.test_id, str(r.page_no_progress)) if r.page_no_progress else None
        if key and r.completion_status == 'completed':
            p['tasks'].add(key)
            p['by_type'].setdefault(ttype, set()).add(key)
            bt['tasks'].add(key)
            _v = (r.verdict or '').strip().lower()
            if _v in ('accept', 'reject'):
                _bucket = 'accepted' if _v == 'accept' else 'rejected'
                p[_bucket].add(key)
                p['type_' + _bucket].setdefault(ttype, set()).add(key)
                bt[_bucket].add(key)
        elif key and r.completion_status == 'skipped':
            p['skipped'].add(key)
            p['type_skipped'].setdefault(ttype, set()).add(key)
            bt['skipped'].add(key)
        else:
            p['drafts'] += 1
            p['type_drafts'][ttype] = p['type_drafts'].get(ttype, 0) + 1
            bt['drafts'] += 1
        if r.time_taken_to_submit:
            secs = r.time_taken_to_submit / 1000.0
            if 0 < secs < 7200:          # ignore tab-left-open outliers
                p['secs'] += secs
                bt['secs'] += secs
        if r.time_of_submission and (p['last'] is None or r.time_of_submission > p['last']):
            p['last'] = r.time_of_submission
        if r.time_of_submission and (bt['last'] is None or r.time_of_submission > bt['last']):
            bt['last'] = r.time_of_submission

    # Batch sizes, looked up only for the batches that actually appear in this window (json_array_length reads the JSON blob, so scanning all ~1k tests is wasteful).
    touched = {tid for pp in per.values() for tid in pp['by_test']}
    size_of_test = {}
    if touched:
        ids = list(touched)
        for chunk in (ids[i:i + 400] for i in range(0, len(ids), 400)):
            rows_ = db.session.execute(
                db.text("SELECT id, json_array_length(json_entry) FROM test WHERE id IN :ids")
                .bindparams(db.bindparam('ids', expanding=True)), {'ids': chunk}
            ).all()
            size_of_test.update({r_[0]: r_[1] or 0 for r_ in rows_})

    raters = {x.id: x for x in Rater.query.all()}
    rows = []
    for rid, p in per.items():
        rt = raters.get(rid)
        rows.append({
            'rater_id': rid,
            'name': rt.name if rt else f'Rater {rid}',
            'email': rt.email if rt else '',
            'completed_tasks': len(p['tasks']),
            # An item completed on one row and skipped on another is paid, not skipped.
            'skipped_tasks': len(p['skipped'] - p['tasks']),
            'draft_tasks': p['drafts'],
            'accepted_tasks': len(p['accepted']),
            'rejected_tasks': len(p['rejected']),
            'by_type': {k: len(v) for k, v in p['by_type'].items()},
            'accepted_by_type': {k: len(v) for k, v in p['type_accepted'].items()},
            'rejected_by_type': {k: len(v) for k, v in p['type_rejected'].items()},
            'submissions_by_type': dict(p['type_subs']),
            'skipped_by_type': {k: len(v - p['tasks']) for k, v in p['type_skipped'].items()},
            'drafts_by_type': dict(p['type_drafts']),
            # Task-wise (per batch) breakdown behind the annotator's period total.
            'by_test': sorted(
                [{
                    'test_id': tid,
                    'test_type': (meta_of_test.get(tid) or (None, None))[0] or 'unknown',
                    'type_label': admin_reports.pretty_test_type(
                        (meta_of_test.get(tid) or (None, None))[0] or 'unknown'),
                    'description': (meta_of_test.get(tid) or (None, ''))[1] or '',
                    'language': admin_reports.test_language((meta_of_test.get(tid) or (None, ''))[1] or ''),
                    'tasks': len(bt['tasks']),
                    'accepted': len(bt['accepted']),
                    'rejected': len(bt['rejected']),
                    'skipped': len(bt['skipped'] - bt['tasks']),
                    'drafts': bt['drafts'],
                    'submissions': bt['subs'],
                    'total_items': size_of_test.get(tid, 0),
                    'hours': round(bt['secs'] / 3600.0, 2),
                    'last_active': bt['last'].isoformat() if bt['last'] else None,
                } for tid, bt in p['by_test'].items()],
                key=lambda x: (-x['tasks'], x['test_id']),
            ),
            'submissions': p['submissions'],
            'hours': round(p['secs'] / 3600.0, 2),
            'avg_seconds': round(p['secs'] / p['submissions'], 1) if p['submissions'] else 0,
            'last_active': p['last'].isoformat() if p['last'] else None,
        })
    rows.sort(key=lambda x: -x['completed_tasks'])

    totals_by_type, totals_subs_by_type = {}, {}
    totals_skipped_by_type, totals_drafts_by_type = {}, {}
    totals_acc_by_type, totals_rej_by_type = {}, {}
    for r in rows:
        for k, v in r['accepted_by_type'].items():
            totals_acc_by_type[k] = totals_acc_by_type.get(k, 0) + v
        for k, v in r['rejected_by_type'].items():
            totals_rej_by_type[k] = totals_rej_by_type.get(k, 0) + v
        for k, v in r['by_type'].items():
            totals_by_type[k] = totals_by_type.get(k, 0) + v
        for k, v in r['submissions_by_type'].items():
            totals_subs_by_type[k] = totals_subs_by_type.get(k, 0) + v
        for k, v in r['skipped_by_type'].items():
            totals_skipped_by_type[k] = totals_skipped_by_type.get(k, 0) + v
        for k, v in r['drafts_by_type'].items():
            totals_drafts_by_type[k] = totals_drafts_by_type.get(k, 0) + v

    # Stable column order for the UI: busiest task type first.
    type_order = sorted(set(totals_by_type) | set(totals_subs_by_type),
                        key=lambda k: (-totals_by_type.get(k, 0), k))

    return jsonify({
        'from': request.args.get('from') or None,
        'to': request.args.get('to') or None,
        'raters': rows,
        'task_types': [
            {'key': k, 'label': admin_reports.pretty_test_type(k),
             'completed_tasks': totals_by_type.get(k, 0),
             'accepted_tasks': totals_acc_by_type.get(k, 0),
             'rejected_tasks': totals_rej_by_type.get(k, 0),
             'skipped_tasks': totals_skipped_by_type.get(k, 0),
             'draft_tasks': totals_drafts_by_type.get(k, 0),
             'submissions': totals_subs_by_type.get(k, 0)}
            for k in type_order
        ],
        'totals': {
            'completed_tasks': sum(r['completed_tasks'] for r in rows),
            'accepted_tasks': sum(r['accepted_tasks'] for r in rows),
            'rejected_tasks': sum(r['rejected_tasks'] for r in rows),
            'skipped_tasks': sum(r['skipped_tasks'] for r in rows),
            'draft_tasks': sum(r['draft_tasks'] for r in rows),
            'submissions': sum(r['submissions'] for r in rows),
            'hours': round(sum(r['hours'] for r in rows), 2),
            'active_raters': len(rows),
            'by_type': totals_by_type,
            'submissions_by_type': totals_subs_by_type,
            'skipped_by_type': totals_skipped_by_type,
            'drafts_by_type': totals_drafts_by_type,
        }
    }), 200


# "Upload QC Task" pane — download an audio-segmentation set straight from a Drive link instead of SSHing in and running load_audio_set.py by hand.
@app.route('/api/admin/qc_upload/inspect', methods=['POST'])
@token_required
def qc_upload_inspect(current_user):
    """Start a background inspection of a Drive recordings link."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    data = request.get_json(silent=True) or {}
    link = (data.get('audio_link') or '').strip()
    if not link:
        return jsonify({'message': 'audio_link is required'}), 400
    if 'drive.google.com' not in link:
        return jsonify({'message': 'That does not look like a Google Drive link.'}), 400

    job = qc_upload_jobs.spawn('inspect', {
        'audio_link': link,
        'id_subfolder': (data.get('id_subfolder') or 'EXPORTED ID').strip(),
        'excel_link': (data.get('excel_link') or '').strip() or None,
    }, 'tools/qc_inspect_worker.py')
    return jsonify(job), 202


@app.route('/api/admin/qc_upload/start', methods=['POST'])
@token_required
def qc_upload_start(current_user):
    """Start the real download + DB load, after the admin confirmed the dialog."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    data = request.get_json(silent=True) or {}
    link = (data.get('audio_link') or '').strip()
    persona = (data.get('persona') or '').strip()
    excel_set = str(data.get('excel_set') or '').strip()
    if not link or not persona or not excel_set:
        return jsonify({'message': 'audio_link, persona and excel_set are required'}), 400

    # One load at a time: load_audio_set.py picks the next free setN when it starts, so two overlapping loads could both claim the same directory.
    busy = qc_upload_jobs.active_load_job()
    if busy:
        return jsonify({'message': 'Another QC upload is still running.',
                        'job': busy}), 409
    # ...and claim the slot atomically, because the check above and the spawn below are two steps across 12 workers.
    if not qc_upload_jobs.acquire_load_lock('pending'):
        return jsonify({'message': 'Another QC upload just started.'}), 409

    job = qc_upload_jobs.spawn('load', {
        'audio_link': link,
        'persona': persona,
        'excel_set': excel_set,
        'language': (data.get('language') or 'english').strip().lower(),
        'set_name': (data.get('set_name') or '').strip(),
        'id_subfolder': (data.get('id_subfolder') or 'EXPORTED ID').strip(),
        'no_load': bool(data.get('no_load')),
    }, 'tools/qc_load_worker.py')
    if job.get('status') == 'failed':
        qc_upload_jobs.release_load_lock()      # never spawned; don't hold the slot
    else:
        qc_upload_jobs.restamp_load_lock(job['id'])
    return jsonify(job), 202


@app.route('/api/admin/qc_upload/jobs', methods=['GET'])
@token_required
def qc_upload_jobs_list(current_user):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    limit = request.args.get('limit', type=int) or 25
    kind = request.args.get('kind') or None
    return jsonify({'jobs': qc_upload_jobs.list_jobs(limit=limit, kind=kind),
                    'active_load': qc_upload_jobs.active_load_job()}), 200


@app.route('/api/admin/qc_upload/job/<job_id>', methods=['GET'])
@token_required
def qc_upload_job_get(current_user, job_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    want_log = request.args.get('log') not in (None, '', '0', 'false')
    job = qc_upload_jobs.get_job(job_id, with_log=want_log)
    if not job:
        return jsonify({'message': 'Job not found'}), 404
    return jsonify(job), 200


@app.route('/api/admin/qc_upload/job/<job_id>', methods=['DELETE'])
@token_required
def qc_upload_job_delete(current_user, job_id):
    """Remove one finished job from the history."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    ok, msg = qc_upload_jobs.delete_job(job_id)
    return jsonify({'message': msg}), (200 if ok else 400)


@app.route('/api/admin/qc_upload/jobs', methods=['DELETE'])
@token_required
def qc_upload_jobs_clear(current_user):
    """Clear the whole history except anything still running."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    from tools import qc_upload_jobs

    n = qc_upload_jobs.clear_finished()
    return jsonify({'message': f'Cleared {n} job(s).', 'deleted': n}), 200


@app.route('/api/admin/qc_upload/job/<job_id>/cancel', methods=['POST'])
@token_required
def qc_upload_job_cancel(current_user, job_id):
    """Stop a running job."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import os as _os
    import signal
    from tools import qc_upload_jobs

    job = qc_upload_jobs.get_job(job_id)
    if not job:
        return jsonify({'message': 'Job not found'}), 404
    pid = job.get('pid')
    if job.get('status') not in ('queued', 'running') or not pid:
        return jsonify({'message': 'Job is not running', 'job': job}), 400
    try:
        _os.killpg(_os.getpgid(pid), signal.SIGTERM)
    except Exception as e:
        app.logger.warning('qc job cancel failed: %s', e)
    job = qc_upload_jobs.update_job(job_id, status='failed',
                                    error='Cancelled by admin.',
                                    progress='cancelled')
    if (job or {}).get('kind') == 'load':
        qc_upload_jobs.release_load_lock()
    return jsonify(job), 200


@app.route('/api/admin/export_tasks_csv', methods=['GET'])
@token_required
def export_tasks_csv(current_user):
    """CSV of tests: Sr."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response

    version = request.args.get('version') or None
    test_type = request.args.get('test_type') or None
    tests = _scoped_tests(_request_team_id(current_user), Test.query.order_by(Test.id)).all()
    # Audio-segmentation rows carry their hours, which needs the reviews.
    ratings_by_test = {}
    if any(t.test_type == 'audio-segmentation' for t in tests):
        for r in Rating.query.yield_per(5000):
            ratings_by_test.setdefault(r.test_id, []).append(r)
    csv_text = admin_reports.tasks_export_csv(tests, test_type=test_type,
                                              version=version,
                                              ratings_by_test=ratings_by_test)
    fname = "tasks_export"
    if test_type:
        fname += f"_{test_type}"
    if version:
        fname += f"_v{version}"
    return Response(
        '\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_audio_clips_csv', methods=['GET'])
@token_required
def export_audio_clips_csv(current_user):
    """Clip-level audio-segmentation export with a playable Saffron deep link per clip."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    import re
    from flask import Response

    # Default: EVERY reviewed clip gets a link. ?rejected_only=1 narrows it.
    only_rejected = request.args.get('rejected_only') in ('1', 'true', 'yes')
    include_pending = request.args.get('include_pending', '1') not in ('0', 'false', 'no')
    language = request.args.get('language') or None
    artist = request.args.get('artist') or None
    tests = Test.query.filter_by(test_type='audio-segmentation').all()
    seg_ids = [t.id for t in tests]
    ratings_by_test = {}
    for r in Rating.query.filter(Rating.test_id.in_(seg_ids)).all():
        ratings_by_test.setdefault(r.test_id, []).append(r)
    csv_text = admin_reports.audio_clips_csv(
        tests, ratings_by_test, only_rejected=only_rejected,
        language=language, include_pending=include_pending, artist=artist
    )
    name = 'audio_clips_rejected' if only_rejected else 'audio_clips_all'
    if language:
        name += '_' + re.sub(r'[^A-Za-z0-9_-]', '', language)
    if artist:
        name += '_' + re.sub(r'[^A-Za-z0-9_-]', '', artist)
    return Response('\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition': f'attachment; filename={name}.csv'})


@app.route('/api/admin/export_artist_report_csv', methods=['GET'])
@token_required
def export_artist_report_csv(current_user):
    """Vendor-shareable CSV: per-artist rejection rates, pending counts + reasons."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    import re
    from flask import Response

    language = request.args.get('language') or None
    artist = request.args.get('artist') or None
    tests = Test.query.filter_by(test_type='audio-segmentation').all()
    seg_ids = [t.id for t in tests]
    ratings_by_test = {}
    for r in Rating.query.filter(Rating.test_id.in_(seg_ids)).all():
        ratings_by_test.setdefault(r.test_id, []).append(r)
    stats = admin_reports.artist_rejection_stats(tests, ratings_by_test,
                                                 language=language, artist=artist)
    name = 'artist_rejection_report'
    if language:
        name += '_' + re.sub(r'[^A-Za-z0-9_-]', '', language)
    if artist:
        name += '_' + re.sub(r'[^A-Za-z0-9_-]', '', artist)
    return Response(
        '\ufeff' + admin_reports.artist_report_csv(stats), mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={name}.csv'}
    )


@app.route('/api/admin/export_audio_hours_csv', methods=['GET'])
@token_required
def export_audio_hours_csv(current_user):
    """CSV: audio-segmentation hours per annotator per IST day, plus a totals row."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import io
    import csv
    import re
    from flask import Response

    try:
        days = max(1, min(int(request.args.get('days', 30)), 365))
    except (TypeError, ValueError):
        days = 30

    # Same two filters the Quality tab applies, so an export matches the screen.
    language = request.args.get('language') or None
    artist_filter = request.args.get('artist') or None
    want_lang = language.strip().lower() if language else None
    want_artist = artist_filter.strip().lower() if artist_filter else None

    try:
        import admin_reports as _ar
    except Exception:
        _ar = None

    tests = Test.query.filter_by(test_type='audio-segmentation').all()
    seg_ids = [t.id for t in tests]
    raters_by_id = {r.id: r for r in Rater.query.all()}
    audio_root = _audio_root()

    per_rater = {}     # rater_id -> {'total': bucket, 'daily': {date: bucket}}
    per_artist = {}    # artist -> coverage bucket
    per_persona = {}
    if seg_ids:
        ratings_by_test = {}
        for r in Rating.query.filter(Rating.test_id.in_(seg_ids)).all():
            ratings_by_test.setdefault(r.test_id, []).append(r)
        for test in tests:
            dur_by_task = _seg_durations_for_test(test, audio_root)
            entries = test.json_entry if isinstance(test.json_entry, list) else []
            set_dir = str(entries[0].get('audio_filename', '')).split('/')[0] if entries else ''
            artist = _ar._recorder_for(set_dir) if (_ar and set_dir) else 'Unknown'
            persona = (entries[0].get('persona') if entries else None) or 'Unknown'
            batch_language = _ar._batch_language(entries) if _ar else 'Unknown'
            if want_lang and batch_language.lower() != want_lang:
                continue
            if want_artist and artist.lower() != want_artist:
                continue
            reviewed_ids = set()
            acc_clips = rej_clips = 0
            acc_secs = rej_secs = 0.0
            for r in ratings_by_test.get(test.id, []):
                if not r.page_no_progress:
                    continue
                agg = per_rater.setdefault(r.rater_id, {'total': _hours_bucket(), 'daily': {}})
                if r.completion_status == 'skipped':
                    agg['total']['skipped'] += 1
                    continue
                if r.completion_status != _SEG_HOURS_STATUS:
                    continue
                secs = dur_by_task.get(str(r.page_no_progress), 0.0)
                agg['total']['clips'] += 1
                agg['total']['seconds'] += secs
                day = agg['daily'].setdefault(_ist_date_str(r.time_of_submission), _hours_bucket())
                day['clips'] += 1
                day['seconds'] += secs
                reviewed_ids.add(str(r.page_no_progress))
                # The verdict column is denormalised out of results_json on write.
                if (r.verdict or '') == 'accept':
                    acc_clips += 1
                    acc_secs += secs
                elif (r.verdict or '') == 'reject':
                    rej_clips += 1
                    rej_secs += secs

            rev_secs = sum(dur_by_task.get(t, 0.0) for t in reviewed_ids)
            tot_secs = sum(dur_by_task.values())
            for key, store in ((artist, per_artist), (persona, per_persona)):
                b = store.setdefault(key, {'batches': 0, 'total_clips': 0,
                                           'total_seconds': 0.0, 'clips': 0,
                                           'seconds': 0.0, 'tags': set(),
                                           'accepted': 0, 'rejected': 0,
                                           'accepted_seconds': 0.0, 'rejected_seconds': 0.0})
                b['batches'] += 1
                b['total_clips'] += len(dur_by_task)
                b['total_seconds'] += tot_secs
                b['clips'] += len(reviewed_ids)
                b['seconds'] += rev_secs
                b['accepted'] += acc_clips
                b['rejected'] += rej_clips
                b['accepted_seconds'] += acc_secs
                b['rejected_seconds'] += rej_secs
                b['tags'].add(persona if store is per_artist else artist)

    out = io.StringIO()
    w = csv.writer(out)

    if language or artist_filter:
        if language:
            w.writerow([f'Language filter: {language}'])
        if artist_filter:
            w.writerow([f'Voice artist filter: {artist_filter}'])
        w.writerow([])

    # Sheet 1 — who did the reviewing, per day.
    w.writerow(['ANNOTATOR HOURS (who reviewed the audio)'])
    w.writerow(['Annotator', 'Email', 'Date (IST)', 'Clips reviewed', 'Audio (hh:mm)',
                'Audio (hours)', 'Audio (seconds)'])
    for rid, agg in sorted(per_rater.items(), key=lambda kv: -kv[1]['total']['seconds']):
        rt = raters_by_id.get(rid)
        name = rt.name if rt else f"Rater {rid}"
        email = rt.email if rt else ""
        for d in _daily_series(agg['daily'], days=days):
            if not d['clips']:
                continue          # only days actually worked
            w.writerow([name, email, d['date'], d['clips'], d['label'], d['hours'],
                        d['seconds']])
        t = _bucket_summary(agg['total'])
        w.writerow([name, email, 'TOTAL (all time)', t['clips'], t['label'], t['hours'],
                    t['seconds']])

    # Sheets 2 & 3 — whose audio it was: QC coverage per artist and per persona.
    for title, store, label, tag_label in (
        ('VOICE ARTIST HOURS (whose audio was reviewed)', per_artist, 'Voice artist', 'Persona(s)'),
        ('PERSONA HOURS (whose audio was reviewed)', per_persona, 'Persona', 'Artist(s)'),
    ):
        w.writerow([])
        w.writerow([title])
        w.writerow([label, tag_label, 'Batches', 'Total clips', 'Total audio',
                    'Clips reviewed', 'Audio reviewed', 'Hours reviewed',
                    'Accepted clips', 'Accepted audio', 'Accepted hours',
                    'Rejected clips', 'Rejected audio', 'Rejected hours',
                    'Audio pending', 'Progress %'])
        for name, b in sorted(store.items(), key=lambda kv: -kv[1]['total_seconds']):
            pending = max(0.0, b['total_seconds'] - b['seconds'])
            w.writerow([
                name, ', '.join(sorted(x for x in b['tags'] if x)), b['batches'],
                b['total_clips'], _hms(b['total_seconds']), b['clips'],
                _hms(b['seconds']), round(b['seconds'] / 3600.0, 2),
                b['accepted'], _hms(b['accepted_seconds']), round(b['accepted_seconds'] / 3600.0, 2),
                b['rejected'], _hms(b['rejected_seconds']), round(b['rejected_seconds'] / 3600.0, 2),
                _hms(pending),
                round(100.0 * b['seconds'] / b['total_seconds'], 1) if b['total_seconds'] else 0.0,
            ])

    fname = f'audio_hours_last_{days}d'
    for _part in (language, artist_filter):
        if _part:
            fname += '_' + re.sub(r'[^A-Za-z0-9_-]', '', _part)
    return Response('\ufeff' + out.getvalue(), mimetype='text/csv; charset=utf-8',
                    headers={'Content-Disposition':
                             f'attachment; filename={fname}.csv'})


@app.route('/api/admin/export_annotators_csv', methods=['GET'])
@token_required
def export_annotators_csv(current_user):
    """CSV export summarizing annotator work: current pending task ID, working on task ID, no."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response
    from datetime import datetime as _dt, timedelta as _td

    def _parse(v):
        try:
            return _dt.strptime(v.strip(), '%Y-%m-%d')
        except Exception:
            return None

    d_from = _parse(request.args.get('from') or '')
    d_to = _parse(request.args.get('to') or '')
    if d_to:
        d_to = d_to + _td(days=1)  # inclusive end day

    rater_id = request.args.get('rater_id', type=int)

    _team_id = _request_team_id(current_user)
    raters = _scoped_raters(_team_id).all()
    tests = _scoped_tests(_team_id).all()
    all_ratings = Rating.query.all()

    ratings_by_rater = {}
    for r in all_ratings:
        ratings_by_rater.setdefault(r.rater_id, []).append(r)

    csv_text = admin_reports.annotators_export_csv(
        raters, tests, ratings_by_rater, d_from=d_from, d_to=d_to, rater_id=rater_id
    )
    fname = "annotators_report"
    if rater_id:
        fname += f"_rater_{rater_id}"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        '\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_annotator_batches_csv', methods=['GET'])
@token_required
def export_annotator_batches_csv(current_user):
    """Task-wise CSV: one row per (annotator, batch) with tasks done in that batch."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response
    from datetime import datetime as _dt, timedelta as _td

    def _parse(v):
        try:
            return _dt.strptime(v.strip(), '%Y-%m-%d')
        except Exception:
            return None

    d_from = _parse(request.args.get('from') or '')
    d_to = _parse(request.args.get('to') or '')
    if d_to:
        d_to = d_to + _td(days=1)  # inclusive end day

    rater_id = request.args.get('rater_id', type=int)

    _team_id = _request_team_id(current_user)
    raters = _scoped_raters(_team_id).all()
    tests = _scoped_tests(_team_id).all()
    ratings_by_rater = {}
    for r in Rating.query.all():
        ratings_by_rater.setdefault(r.rater_id, []).append(r)

    csv_text = admin_reports.annotator_batches_csv(
        raters, tests, ratings_by_rater, d_from=d_from, d_to=d_to, rater_id=rater_id
    )
    fname = "annotator_tasks_by_batch"
    if rater_id:
        fname += f"_rater_{rater_id}"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        '\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_rater_ratings_csv/<int:rater_id>', methods=['GET'])
@token_required
def export_rater_ratings_csv(current_user, rater_id):
    """Detailed line-by-line CSV of all ratings submitted by a specific rater within optional date bounds."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response
    from datetime import datetime as _dt, timedelta as _td

    rater = Rater.query.get(rater_id)
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404

    def _parse(v):
        try:
            return _dt.strptime(v.strip(), '%Y-%m-%d')
        except Exception:
            return None

    d_from = _parse(request.args.get('from') or '')
    d_to = _parse(request.args.get('to') or '')

    q = Rating.query.filter_by(rater_id=rater_id)
    if d_from:
        q = q.filter(Rating.time_of_submission >= d_from)
    if d_to:
        q = q.filter(Rating.time_of_submission < d_to + _td(days=1))
    ratings = q.order_by(Rating.time_of_submission.desc()).all()

    tests = _scoped_tests(_request_team_id(current_user)).all()
    csv_text = admin_reports.rater_detailed_ratings_csv(rater, tests, ratings)

    r_name = rater.name.replace(' ', '_')
    fname = f"annotations_rater_{rater_id}_{r_name}"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        '\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_all_ratings_csv', methods=['GET'])
@token_required
def export_all_ratings_csv(current_user):
    """Detailed line-by-line CSV of all ratings submitted across all raters within optional date bounds."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response
    from datetime import datetime as _dt, timedelta as _td

    def _parse(v):
        try:
            return _dt.strptime(v.strip(), '%Y-%m-%d')
        except Exception:
            return None

    d_from = _parse(request.args.get('from') or '')
    d_to = _parse(request.args.get('to') or '')

    q = Rating.query
    if d_from:
        q = q.filter(Rating.time_of_submission >= d_from)
    if d_to:
        q = q.filter(Rating.time_of_submission < d_to + _td(days=1))
    ratings = q.order_by(Rating.time_of_submission.desc()).all()

    _team_id = _request_team_id(current_user)
    raters = _scoped_raters(_team_id).all()
    tests = _scoped_tests(_team_id).all()
    csv_text = admin_reports.all_detailed_ratings_csv(raters, tests, ratings)

    fname = "all_annotations_report"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        '\ufeff' + csv_text, mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )





import json as _json_mod  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
json = _json_mod

# Dashboard payload cache (shared across gunicorn workers via a temp file).
_DASHBOARD_CACHE = os.path.join(tempfile.gettempdir(), 'saffron_dashboard_cache.json')
_DASHBOARD_CACHE_TTL = int(os.environ.get('DASHBOARD_CACHE_TTL', '60'))


def _dashboard_cache_path(team_id=None):
    """One cache file per team -- a TTS admin's payload must never be served to an ASR admin (and vice versa)."""
    if team_id is None:
        return _DASHBOARD_CACHE
    return f"{_DASHBOARD_CACHE}.team{team_id}"


def _dashboard_cache_read(team_id=None):
    """Return (payload, age_seconds) if a fresh cache exists, else (None, None)."""
    path = _dashboard_cache_path(team_id)
    try:
        age = time.time() - os.path.getmtime(path)
        if age > _DASHBOARD_CACHE_TTL:
            return None, None
        with open(path, encoding='utf-8') as fh:
            return json.load(fh), age
    except Exception:
        return None, None


def _dashboard_cache_write(payload, team_id=None):
    path = _dashboard_cache_path(team_id)
    try:
        tmp = path + f'.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)   # atomic; concurrent workers can't tear it
    except Exception as e:
        print(f"[WARN] dashboard cache write failed: {e}")


def _dashboard_cache_invalidate():
    """Drop the cached dashboard payload so the next GET recomputes from the DB."""
    import glob as _glob
    for path in [_DASHBOARD_CACHE] + _glob.glob(_DASHBOARD_CACHE + '.team*'):
        if path.endswith('.tmp'):
            continue
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"[WARN] dashboard cache invalidate failed: {e}")


@app.route('/api/admin/task/<int:test_id>/annotations', methods=['GET'])
@token_required
def get_task_annotations(current_user, test_id):
    """Admin-only: the submitted annotations for one task, grouped by annotator."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401

    test = Test.query.filter_by(id=test_id).first_or_404()
    items = test.json_entry if isinstance(test.json_entry, list) else []

    # Group ratings by rater, keeping the latest submission per (rater, item).
    ratings = Rating.query.filter_by(test_id=test_id).all()
    by_rater = {}  # rater_id -> { item_id(str) -> Rating }
    for r in ratings:
        item_id = str(r.page_no_progress) if r.page_no_progress is not None else None
        if item_id is None and isinstance(r.results_json, dict):
            item_id = str(r.results_json.get('id')) if r.results_json.get('id') is not None else None
        if item_id is None:
            continue
        slot = by_rater.setdefault(r.rater_id, {})
        prev = slot.get(item_id)
        if prev is None or r.time_of_submission > prev.time_of_submission:
            slot[item_id] = r

    # Look up annotator names/emails in one query.
    rater_ids = list(by_rater.keys())
    raters = {rt.id: rt for rt in Rater.query.filter(Rater.id.in_(rater_ids)).all()} if rater_ids else {}

    def _verdict(results):
        """Normalize an accept/reject decision across task types (benchmark uses 'decision', conversation/audio use 'evaluation')."""
        if not isinstance(results, dict):
            return None
        v = results.get('decision') or results.get('evaluation')
        return str(v).strip().lower() if v else None

    annotators = []
    for rater_id, slot in by_rater.items():
        rt = raters.get(rater_id)
        counts = {'completed': 0, 'skipped': 0, 'saved': 0, 'accepted': 0, 'rejected': 0}
        ratings_out = {}
        for item_id, r in slot.items():
            status = r.completion_status or 'completed'
            if status in counts:
                counts[status] += 1
            v = _verdict(r.results_json)
            if v == 'accept':
                counts['accepted'] += 1
            elif v == 'reject':
                counts['rejected'] += 1
            ratings_out[item_id] = {
                'status': status,
                'verdict': v,
                'time': r.time_of_submission.isoformat() if r.time_of_submission else None,
                'results': r.results_json,
            }
        annotators.append({
            'rater_id': rater_id,
            'name': rt.name if rt else f'Rater #{rater_id}',
            'email': rt.email if rt else '',
            'counts': counts,
            'ratings': ratings_out,
        })

    # Most-active annotator first.
    annotators.sort(key=lambda a: a['counts']['completed'] + a['counts']['skipped'], reverse=True)

    return jsonify({
        'test_id': test.id,
        'description': test.description,
        'test_type': test.test_type,
        'handoff_mode': bool(getattr(test, 'handoff_mode', False)),
        'total_items': len(items),
        'items': items,
        'annotators': annotators,
    })


@app.route('/api/admin/task/<int:test_id>/handoff', methods=['POST'])
@token_required
def set_task_handoff(current_user, test_id):
    """Admin-only: toggle a task's handoff mode."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    test = Test.query.filter_by(id=test_id).first_or_404()
    data = request.get_json() or {}
    test.handoff_mode = bool(data.get('enabled'))
    db.session.commit()
    _dashboard_cache_invalidate()
    return jsonify({'test_id': test.id, 'handoff_mode': bool(test.handoff_mode)}), 200


@app.route('/api/admin/dashboard', methods=['GET'])
@token_required
def get_admin_dashboard(current_user):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401

    # Which team's dashboard this is: a team admin is pinned to their own team, an org admin may target one with ?team=<key> (defaults to TTS).
    team_id = _request_team_id(current_user)

    if request.args.get('refresh') not in ('1', 'true', 'yes'):
        _cached, _age = _dashboard_cache_read(team_id)
        if _cached is not None:
            _cached['_cache'] = {'hit': True, 'age_seconds': round(_age, 1),
                                 'ttl': _DASHBOARD_CACHE_TTL}
            return jsonify(_cached)

    try:
        from sqlalchemy.orm import defer
        import re

        # 1. Fetch this team's raters and ratings once to avoid N+1 queries
        raters = _scoped_raters(team_id).all()
        total_registered_users = len(raters)

        # Only this team's batches -- and therefore only this team's ratings.
        team_test_ids = _team_test_ids(team_id)

        # Only these seven columns are ever read from a rating here.
        _ratings_q = db.session.query(
            Rating.id, Rating.rater_id, Rating.test_id, Rating.page_no_progress,
            Rating.completion_status, Rating.time_of_submission,
            Rating.time_taken_to_submit, Rating.verdict,
        )
        if team_test_ids is not None:
            _ratings_q = _ratings_q.filter(Rating.test_id.in_(team_test_ids))
        all_ratings = _ratings_q.all()

        # The per-batch accept/reject tallies need one field out of results_json.
        eval_by_rating = {r.id: (r.verdict or '') for r in all_ratings}
        
        # Group ratings in memory
        ratings_by_rater = {}
        ratings_by_test = {}
        for r in all_ratings:
            ratings_by_rater.setdefault(r.rater_id, []).append(r)
            ratings_by_test.setdefault(r.test_id, []).append(r)
            
        raters_data = []
        active_users_count = 0

        # How many messages the admin has already sent each annotator (for the UI badge).
        msg_count_by_rater = {}
        try:
            for rid, cnt in db.session.query(Message.rater_id, db.func.count(Message.id)).group_by(Message.rater_id).all():
                msg_count_by_rater[rid] = cnt
        except Exception:
            msg_count_by_rater = {}

        for rater in raters:
            rater_ratings = ratings_by_rater.get(rater.id, [])
            # Key on (test_id, item): item ids restart at 1 in every batch, so a bare item id silently merges tasks from different batches into one.
            completed_tasks_count = len({(r.test_id, r.page_no_progress) for r in rater_ratings if r.page_no_progress and r.completion_status in ['completed', 'skipped']})
            
            last_active = None
            if rater_ratings:
                last_active_dt = max(r.time_of_submission for r in rater_ratings)
                last_active = last_active_dt.isoformat()
            
            is_active = completed_tasks_count > 0
            if is_active:
                active_users_count += 1
                
            status_text = f"{completed_tasks_count} Tasks Completed" if completed_tasks_count != 1 else "1 Task Completed"
            raters_data.append({
                'id': rater.id,
                'name': rater.name,
                'email': rater.email,
                'gender': rater.gender,
                'age': rater.age,
                'completed_tasks_count': completed_tasks_count,
                'last_active': last_active,
                'status': status_text,
                'assigned_tasks': rater.assigned_tasks or "",
                'account_active': bool(getattr(rater, 'is_active', True)),
                'messages_sent': msg_count_by_rater.get(rater.id, 0)
            })
            
        pending_registrations_count = total_registered_users - active_users_count
        
        tests = _scoped_tests(team_id, Test.query.options(defer(Test.json_entry))).all()

        # json_entry is deferred, so ANY attribute access on it costs an extra SELECT of a multi-MB blob.
        size_by_test = {t.id: (t.item_count or 0) for t in tests}
        lang_by_test = {t.id: t.language_hint.capitalize()
                        for t in tests if t.language_hint}
        total_tests_count = len(tests)
        
        # Configured languages plus every language already seen in this team's data, longest name first so e.g. 'hindi' never shadows a longer match.
        languages_list = sorted(
            set(KNOWN_LANGUAGES) | {v.strip().lower() for v in lang_by_test.values() if v},
            key=len, reverse=True)

        tests_data = []
        languages_map = {}
        
        total_global_tasks = 0
        total_global_unique_completed = 0
        total_global_submissions = 0
        
        for test in tests:
            desc = test.description or "No description"

            # Infer language from description first (very fast)
            lang = _infer_language(desc, languages_list)
            if not lang:
                # Fallback to the first item's language, read in the bulk pre-pass above rather than by lazy-loading this batch's whole json_entry.
                lang = lang_by_test.get(test.id) or "Unknown"
            
            # Parse total tasks count from description if available (Tasks X to Y)
            total_tasks = 0
            match = re.search(r"Tasks (\d+) to (\d+)", desc)
            if match:
                total_tasks = int(match.group(2)) - int(match.group(1)) + 1
            else:
                total_tasks = size_by_test.get(test.id, 0)
                
            test_ratings = ratings_by_test.get(test.id, [])
            unique_completed = len({r.page_no_progress for r in test_ratings if r.page_no_progress and r.completion_status in ['completed', 'skipped']})
            total_submissions = len([r for r in test_ratings if r.completion_status in ['completed', 'skipped']])
            
            # Parse version from description
            version = ""
            version_match = re.search(r"version\s*([0-9a-zA-Z_-]+)", desc, re.IGNORECASE)
            if version_match:
                version = f"Version {version_match.group(1)}"
            elif "new version" in desc.lower():
                version = "New Version"
            else:
                version = "V1 / Default"

            tests_data.append({
                'id': test.id,
                'description': desc,
                'test_type': test.test_type,
                'language': lang,
                'version': version,
                'total_tasks': total_tasks,
                'unique_completed_tasks': unique_completed,
                'total_submissions': total_submissions
            })
            
            languages_map.setdefault(lang, {
                'language': lang,
                'test_count': 0,
                'total_tasks': 0,
                'unique_completed_tasks': 0,
                'total_submissions': 0
            })
            languages_map[lang]['test_count'] += 1
            languages_map[lang]['total_tasks'] += total_tasks
            languages_map[lang]['unique_completed_tasks'] += unique_completed
            languages_map[lang]['total_submissions'] += total_submissions
            
            total_global_tasks += total_tasks
            total_global_unique_completed += unique_completed
            total_global_submissions += total_submissions
            
        languages_data = list(languages_map.values())
        languages_data.sort(key=lambda x: x['language'])


        # Audio-segmentation ratings need results_json (evaluation / rejection_reasons).
        seg_test_ids = [t.id for t in tests if t.test_type == 'audio-segmentation']
        seg_ratings_by_test = {}
        if seg_test_ids:
            for _r in Rating.query.filter(Rating.test_id.in_(seg_test_ids)).all():
                seg_ratings_by_test.setdefault(_r.test_id, []).append(_r)

        # 3.
        import os as _os
        audio_root = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            'audio_segmentation'
        )
        raters_by_id = {r.id: r for r in raters}
        audio_seg_data = []
        # Per-annotator audio hours (cumulative + per IST day), accumulated as the loop below already has each batch's clip durations in hand.
        hours_by_rater = {}
        hours_daily_all = {}
        # Per voice-artist / per persona audio hours: of the audio THIS ARTIST recorded, how much has been QC'd.
        hours_by_artist = {}
        hours_by_persona = {}
        # Filterable hours: one row per batch (the denominators) plus one fact per
        # (annotator, batch, IST day). The Quality tab re-rolls these client-side so
        # every number on the page follows its language / artist filter.
        hours_by_batch = []
        hours_facts = {}
        # Clips whose stored rejection reason is no longer offered in the UI (e.g.
        retired_clips = []
        try:
            import admin_reports as _ar
        except Exception as _e:
            print(f"[WARN] admin_reports unavailable for artist hours: {_e}")
            _ar = None
        _seg_entries = {}
        _seg_ids = [t.id for t in tests if t.test_type == 'audio-segmentation']
        if _seg_ids:
            for _t in Test.query.filter(Test.id.in_(_seg_ids)).all():
                _seg_entries[_t.id] = _t.json_entry if isinstance(_t.json_entry, list) else []

        for test in tests:
            if test.test_type != 'audio-segmentation':
                continue
            entries = _seg_entries.get(test.id, [])
            dur_by_task = {}
            lang_counts = {}
            persona_counts = {}
            for item in entries:
                task_id = str(item.get('id') or '')
                filename = item.get('audio_filename')
                # Track the language / persona of this batch (single-valued per set, but count occurrences and pick the most common to be safe).
                il = item.get('language')
                if il:
                    lang_counts[il] = lang_counts.get(il, 0) + 1
                ip = item.get('persona')
                if ip:
                    persona_counts[ip] = persona_counts.get(ip, 0) + 1
                if not task_id or not filename:
                    continue
                dur_by_task[task_id] = _wav_duration_seconds(
                    _os.path.join(audio_root, filename)
                )
            total_secs = sum(dur_by_task.values())

            seg_language = max(lang_counts, key=lang_counts.get) if lang_counts else "Unknown"
            seg_persona = max(persona_counts, key=persona_counts.get) if persona_counts else "Unknown"
            # Voice artist of this batch. Resolved here (not after the ratings loop)
            # because the retired-clip rows and the hours facts below both need it.
            _set_dir = str(entries[0].get('audio_filename', '')).split('/')[0] if entries else ''
            _artist = _ar._recorder_for(_set_dir) if (_ar and _set_dir) else 'Unknown'

            # Distinct completed task ids per rater for this test + accept/reject tallies read from each submission's results_json ("evaluation" field).
            done_by_rater = {}
            eval_by_rater = {}   # rater_id -> [accepted, rejected]
            seg_accepted = 0
            seg_rejected = 0
            # Audio behind those verdicts. Counted per submission, exactly like
            # the accept/reject tallies, so hours and counts always agree.
            seg_accepted_secs = 0.0
            seg_rejected_secs = 0.0
            # Clip ids REVIEWED at least once, deduped: two annotators reviewing the same clip must not make the artist look twice as far along.
            seg_reviewed_ids = set()
            seg_reviewed_today_ids = set()
            for r in seg_ratings_by_test.get(test.id, []):
                if not (r.page_no_progress and r.completion_status in ['completed', 'skipped']):
                    continue
                # --- audio hours (reviewed clips only; skips carry no hours) ---
                hb = hours_by_rater.setdefault(r.rater_id, {
                    'total': _hours_bucket(), 'daily': {}, 'last': None,
                    'batches': set(), 'accepted': 0, 'rejected': 0,
                })
                _secs = dur_by_task.get(str(r.page_no_progress), 0.0)
                _fd = _ist_date_str(r.time_of_submission)
                _fact = hours_facts.setdefault((r.rater_id, test.id, _fd), {
                    'rater_id': r.rater_id, 'test_id': test.id, 'date': _fd,
                    'clips': 0, 'seconds': 0.0, 'skipped': 0,
                    'accepted': 0, 'rejected': 0,
                    'accepted_seconds': 0.0, 'rejected_seconds': 0.0, 'last': None,
                })
                if r.completion_status == 'skipped':
                    hb['total']['skipped'] += 1
                    _fact['skipped'] += 1
                else:
                    hb['total']['clips'] += 1
                    hb['total']['seconds'] += _secs
                    _fact['clips'] += 1
                    _fact['seconds'] += _secs
                    # "last activity" counts reviews only, exactly as hb['last'] does
                    if _fact['last'] is None or (
                            r.time_of_submission and r.time_of_submission > _fact['last']):
                        _fact['last'] = r.time_of_submission
                    hb['batches'].add(test.id)
                    _d = _ist_date_str(r.time_of_submission)
                    for _tgt in (hb['daily'].setdefault(_d, _hours_bucket()),
                                 hours_daily_all.setdefault(_d, _hours_bucket())):
                        _tgt['clips'] += 1
                        _tgt['seconds'] += _secs
                    if hb['last'] is None or r.time_of_submission > hb['last']:
                        hb['last'] = r.time_of_submission
                    seg_reviewed_ids.add(str(r.page_no_progress))
                    if _d == _ist_today_str():
                        seg_reviewed_today_ids.add(str(r.page_no_progress))

                done_by_rater.setdefault(r.rater_id, set()).add(str(r.page_no_progress))
                rj = r.results_json if isinstance(r.results_json, dict) else {}
                ev = str(rj.get('evaluation') or '').strip().lower()
                tally = eval_by_rater.setdefault(r.rater_id, [0, 0])
                if ev == 'accept':
                    seg_accepted += 1
                    seg_accepted_secs += _secs
                    tally[0] += 1
                    hb['accepted'] += 1
                    _fact['accepted'] += 1
                    _fact['accepted_seconds'] += _secs
                elif ev == 'reject':
                    seg_rejected += 1
                    seg_rejected_secs += _secs
                    tally[1] += 1
                    hb['rejected'] += 1
                    _fact['rejected'] += 1
                    _fact['rejected_seconds'] += _secs
                    # Flag a reason the UI no longer offers, so it can be re-done.
                    _retired = _ar.retired_reasons_of(rj) if _ar else []
                    if _retired:
                        _rt = raters_by_id.get(r.rater_id)
                        retired_clips.append({
                            'rating_id': r.id,
                            'rater_id': r.rater_id,
                            'rater_name': _rt.name if _rt else f"Rater {r.rater_id}",
                            'rater_email': _rt.email if _rt else "",
                            'test_id': test.id,
                            'description': test.description or "No description",
                            'clip_id': str(r.page_no_progress),
                            'retired_reasons': _retired,
                            'all_reasons': _ar._reasons_of(rj) if _ar else [],
                            'custom_reason': rj.get('custom_rejection_reason') or "",
                            'comments': rj.get('comments') or "",
                            'persona': seg_persona,
                            'language': seg_language,
                            'artist': _artist,
                            'submitted': r.time_of_submission.isoformat() if r.time_of_submission else None,
                            'link': f"{_SAFFRON_BASE_URL}/{test.id}?task={r.page_no_progress}",
                        })

            unique_done = set().union(*done_by_rater.values()) if done_by_rater else set()
            annotators = []
            for rater_id, task_ids in done_by_rater.items():
                rater = raters_by_id.get(rater_id)
                secs = sum(dur_by_task.get(t, 0.0) for t in task_ids)
                tally = eval_by_rater.get(rater_id, [0, 0])
                annotators.append({
                    'rater_id': rater_id,
                    'name': rater.name if rater else f"Rater {rater_id}",
                    'email': rater.email if rater else "",
                    'completed_tasks': len(task_ids),
                    'completed_audio_seconds': round(secs, 1),
                    'accepted': tally[0],
                    'rejected': tally[1]
                })
            annotators.sort(key=lambda a: -a['completed_audio_seconds'])

            audio_seg_data.append({
                'test_id': test.id,
                'description': test.description or "No description",
                'language': seg_language,
                'persona': seg_persona,
                'total_tasks': len(dur_by_task),
                'total_audio_seconds': round(total_secs, 1),
                'completed_tasks': len(unique_done),
                'completed_audio_seconds': round(
                    sum(dur_by_task.get(t, 0.0) for t in unique_done), 1
                ),
                'accepted': seg_accepted,
                'rejected': seg_rejected,
                'total_submissions': seg_accepted + seg_rejected,
                'annotators': annotators
            })

            # --- roll this batch into its voice artist + persona ---
            _rev_secs = sum(dur_by_task.get(t, 0.0) for t in seg_reviewed_ids)
            _today_secs = sum(dur_by_task.get(t, 0.0) for t in seg_reviewed_today_ids)
            for _key, _store in ((_artist, hours_by_artist), (seg_persona, hours_by_persona)):
                _b = _store.setdefault(_key, {
                    'batches': 0, 'total_clips': 0, 'total_seconds': 0.0,
                    'clips': 0, 'seconds': 0.0, 'today_clips': 0, 'today_seconds': 0.0,
                    'accepted': 0, 'rejected': 0, 'accepted_seconds': 0.0,
                    'rejected_seconds': 0.0, 'personas': set(), 'artists': set(),
                    'languages': set(), 'test_ids': [],
                })
                _b['batches'] += 1
                _b['total_clips'] += len(dur_by_task)
                _b['total_seconds'] += total_secs
                _b['clips'] += len(seg_reviewed_ids)
                _b['seconds'] += _rev_secs
                _b['today_clips'] += len(seg_reviewed_today_ids)
                _b['today_seconds'] += _today_secs
                _b['accepted'] += seg_accepted
                _b['rejected'] += seg_rejected
                _b['accepted_seconds'] += seg_accepted_secs
                _b['rejected_seconds'] += seg_rejected_secs
                _b['personas'].add(seg_persona)
                _b['artists'].add(_artist)
                _b['languages'].add(seg_language)
                _b['test_ids'].append(test.id)

            hours_by_batch.append({
                'test_id': test.id,
                'description': test.description or '',
                'artist': _artist,
                'persona': seg_persona,
                'language': seg_language,
                'total_clips': len(dur_by_task),
                'total_seconds': round(total_secs, 1),
                # reviewed = deduped across annotators, same as the coverage rows
                'clips': len(seg_reviewed_ids),
                'seconds': round(_rev_secs, 1),
                'today_clips': len(seg_reviewed_today_ids),
                'today_seconds': round(_today_secs, 1),
                'accepted': seg_accepted,
                'rejected': seg_rejected,
                'accepted_seconds': round(seg_accepted_secs, 1),
                'rejected_seconds': round(seg_rejected_secs, 1),
            })

        audio_seg_data.sort(key=lambda x: x['test_id'])

        # 3b.
        _today = _ist_today_str()
        _hours_annotators = []
        _grand = _hours_bucket()
        for _rid, hb in hours_by_rater.items():
            if not (hb['total']['clips'] or hb['total']['skipped']):
                continue
            _rt = raters_by_id.get(_rid)
            _series = _daily_series(hb['daily'], days=30)
            _week = _hours_bucket()
            for _d in _series[:7]:
                _week['clips'] += _d['clips']
                _week['seconds'] += _d['seconds']
            _active = sum(1 for b in hb['daily'].values() if b['clips'])
            _row = _bucket_summary(hb['total'])
            _row.update({
                'rater_id': _rid,
                'name': _rt.name if _rt else f"Rater {_rid}",
                'email': _rt.email if _rt else "",
                'is_active': bool(_rt.is_active) if _rt else True,
                'batches': len(hb['batches']),
                'accepted': hb['accepted'],
                'rejected': hb['rejected'],
                'today': _bucket_summary(hb['daily'].get(_today) or _hours_bucket()),
                'last_7_days': _bucket_summary(_week),
                'active_days': _active,
                'avg_per_active_day': _bucket_summary({
                    'clips': round(hb['total']['clips'] / _active) if _active else 0,
                    'seconds': (hb['total']['seconds'] / _active) if _active else 0.0,
                    'skipped': 0,
                }),
                'daily_series': _series,
                'last_activity': hb['last'].isoformat() if hb['last'] else None,
            })
            _hours_annotators.append(_row)
            _grand['clips'] += hb['total']['clips']
            _grand['seconds'] += hb['total']['seconds']
            _grand['skipped'] += hb['total']['skipped']
        _hours_annotators.sort(key=lambda a: -a['seconds'])

        _all_series = _daily_series(hours_daily_all, days=30)
        _all_week = _hours_bucket()
        for _d in _all_series[:7]:
            _all_week['clips'] += _d['clips']
            _all_week['seconds'] += _d['seconds']

        def _coverage_rows(store, name_key, other_key):
            """Serialise an artist/persona bucket: how much of the audio that this artist (or persona) recorded has been QC'd, and how much is left."""
            rows = []
            for _name, b in store.items():
                pending_clips = max(0, b['total_clips'] - b['clips'])
                pending_secs = max(0.0, b['total_seconds'] - b['seconds'])
                rows.append({
                    name_key: _name,
                    other_key: sorted(x for x in b[other_key] if x),
                    'languages': sorted(x for x in b['languages'] if x),
                    'batches': b['batches'],
                    'total_clips': b['total_clips'],
                    'total_seconds': round(b['total_seconds'], 1),
                    'total_label': _hms(b['total_seconds']),
                    # "hours completed" = audio actually reviewed
                    'clips': b['clips'],
                    'seconds': round(b['seconds'], 1),
                    'hours': round(b['seconds'] / 3600.0, 2),
                    'label': _hms(b['seconds']),
                    'pending_clips': pending_clips,
                    'pending_seconds': round(pending_secs, 1),
                    'pending_label': _hms(pending_secs),
                    'today_clips': b['today_clips'],
                    'today_label': _hms(b['today_seconds']),
                    'today_seconds': round(b['today_seconds'], 1),
                    'accepted': b['accepted'],
                    'rejected': b['rejected'],
                    'accepted_seconds': round(b['accepted_seconds'], 1),
                    'accepted_label': _hms(b['accepted_seconds']),
                    'rejected_seconds': round(b['rejected_seconds'], 1),
                    'rejected_label': _hms(b['rejected_seconds']),
                    'rejection_rate': round(
                        100.0 * b['rejected'] / (b['accepted'] + b['rejected']), 1
                    ) if (b['accepted'] + b['rejected']) else 0.0,
                    'progress': round(
                        100.0 * b['seconds'] / b['total_seconds'], 1
                    ) if b['total_seconds'] else 0.0,
                    'test_ids': sorted(b['test_ids']),
                })
            rows.sort(key=lambda x: -x['total_seconds'])
            return rows

        audio_hours_data = {
            'timezone': 'IST (UTC+5:30)',
            'today_date': _today,
            'totals': _bucket_summary(_grand),
            'today': _bucket_summary(hours_daily_all.get(_today) or _hours_bucket()),
            'last_7_days': _bucket_summary(_all_week),
            'active_today': sum(1 for a in _hours_annotators if a['today']['clips']),
            'annotators': _hours_annotators,
            'daily_series': _all_series,
            'by_artist': _coverage_rows(hours_by_artist, 'artist', 'personas'),
            'by_persona': _coverage_rows(hours_by_persona, 'persona', 'artists'),
            'by_batch': sorted(hours_by_batch, key=lambda b: b['test_id']),
            'facts': [
                {'rater_id': f['rater_id'], 'test_id': f['test_id'], 'date': f['date'],
                 'clips': f['clips'], 'skipped': f['skipped'],
                 'seconds': round(f['seconds'], 1),
                 'accepted': f['accepted'], 'rejected': f['rejected'],
                 'accepted_seconds': round(f['accepted_seconds'], 1),
                 'rejected_seconds': round(f['rejected_seconds'], 1),
                 'last': f['last'].isoformat() if f['last'] else None}
                for f in hours_facts.values()
            ],
        }

        # Clips still carrying a rejection reason the UI has retired.
        retired_clips.sort(key=lambda c: (c['rater_name'], c['test_id'], c['clip_id']))
        _retired_counts = {}
        for _c in retired_clips:
            for _s in _c['retired_reasons']:
                _retired_counts[_s] = _retired_counts.get(_s, 0) + 1
        retired_reason_data = {
            'clips': retired_clips,
            'total': len(retired_clips),
            'by_reason': sorted(
                ({'reason': k, 'label': k.replace('_', ' ').title(), 'count': v}
                 for k, v in _retired_counts.items()),
                key=lambda x: -x['count']
            ),
        }

        # 4.
        assigned_by_test = {}
        for rater in raters:
            for tid_str in (rater.assigned_tasks or "").split(','):
                tid_str = tid_str.strip()
                if tid_str.isdigit():
                    assigned_by_test.setdefault(int(tid_str), []).append(rater.name)

        task_types_map = {}
        for td in tests_data:
            test_ratings = ratings_by_test.get(td['id'], [])

            per_rater = {}
            batch_accepted = batch_rejected = batch_skipped = batch_saved = 0
            batch_last = None
            batch_time_sum = 0.0
            batch_time_n = 0
            for r in test_ratings:
                pr = per_rater.setdefault(r.rater_id, {
                    'done': set(), 'accepted': 0, 'rejected': 0, 'skipped': 0,
                    'saved': 0, 'time_sum': 0.0, 'time_n': 0, 'last': None
                })
                if batch_last is None or r.time_of_submission > batch_last:
                    batch_last = r.time_of_submission
                if pr['last'] is None or r.time_of_submission > pr['last']:
                    pr['last'] = r.time_of_submission
                if r.completion_status == 'saved':
                    batch_saved += 1
                    pr['saved'] += 1
                    continue
                if r.completion_status not in ['completed', 'skipped']:
                    continue
                if r.page_no_progress:
                    pr['done'].add(str(r.page_no_progress))
                if r.completion_status == 'skipped':
                    batch_skipped += 1
                    pr['skipped'] += 1
                if r.time_taken_to_submit:
                    secs = r.time_taken_to_submit / 1000.0
                    if 0 < secs < 7200:  # ignore outliers (left tab open etc.)
                        batch_time_sum += secs
                        batch_time_n += 1
                        pr['time_sum'] += secs
                        pr['time_n'] += 1
                if eval_by_rating is not None:
                    ev = eval_by_rating.get(r.id, '')
                else:
                    _rj = getattr(r, 'results_json', None)
                    ev = str((_rj or {}).get('evaluation') or '').strip().lower() if isinstance(_rj, dict) else ''
                if ev == 'accept':
                    batch_accepted += 1
                    pr['accepted'] += 1
                elif ev == 'reject':
                    batch_rejected += 1
                    pr['rejected'] += 1

            annotators = []
            for rid, pr in per_rater.items():
                rater = raters_by_id.get(rid)
                annotators.append({
                    'rater_id': rid,
                    'name': rater.name if rater else f"Rater {rid}",
                    'email': rater.email if rater else "",
                    'completed': len(pr['done']),
                    'accepted': pr['accepted'],
                    'rejected': pr['rejected'],
                    'skipped': pr['skipped'],
                    'in_progress': pr['saved'],
                    'avg_secs': round(pr['time_sum'] / pr['time_n'], 1) if pr['time_n'] else None,
                    'last_activity': pr['last'].isoformat() if pr['last'] else None
                })
            annotators.sort(key=lambda a: -a['completed'])

            batch = {
                'test_id': td['id'],
                'description': td['description'],
                'language': td['language'],
                'version': td['version'],
                'total_tasks': td['total_tasks'],
                'unique_completed': td['unique_completed_tasks'],
                'total_submissions': td['total_submissions'],
                'accepted': batch_accepted,
                'rejected': batch_rejected,
                'skipped': batch_skipped,
                'in_progress': batch_saved,
                'avg_secs': round(batch_time_sum / batch_time_n, 1) if batch_time_n else None,
                'last_activity': batch_last.isoformat() if batch_last else None,
                'assigned_to': assigned_by_test.get(td['id'], []),
                'annotators': annotators
            }

            tt = task_types_map.setdefault(td['test_type'], {
                'batches': [],
                'totals': {
                    'batches': 0, 'total_tasks': 0, 'unique_completed': 0,
                    'total_submissions': 0, 'accepted': 0, 'rejected': 0,
                    'skipped': 0, 'in_progress': 0,
                    'batches_complete': 0, 'batches_stalled': 0, 'batches_unassigned': 0,
                    'annotator_ids': set(), 'last_activity': None
                }
            })
            tt['batches'].append(batch)
            tot = tt['totals']
            tot['batches'] += 1
            tot['total_tasks'] += batch['total_tasks']
            tot['unique_completed'] += batch['unique_completed']
            tot['total_submissions'] += batch['total_submissions']
            tot['accepted'] += batch_accepted
            tot['rejected'] += batch_rejected
            tot['skipped'] += batch_skipped
            tot['in_progress'] += batch_saved
            if batch['total_tasks'] and batch['unique_completed'] >= batch['total_tasks']:
                tot['batches_complete'] += 1
            if batch['total_submissions'] == 0:
                tot['batches_stalled'] += 1
            if not batch['assigned_to']:
                tot['batches_unassigned'] += 1
            tot['annotator_ids'].update(per_rater.keys())
            if batch_last and (tot['last_activity'] is None or batch_last > tot['last_activity']):
                tot['last_activity'] = batch_last

        task_types_data = {}
        for tt_name, tt in task_types_map.items():
            tt['batches'].sort(key=lambda b: b['test_id'])
            tot = tt['totals']
            tot['annotators'] = len(tot.pop('annotator_ids'))
            tot['last_activity'] = tot['last_activity'].isoformat() if tot['last_activity'] else None
            task_types_data[tt_name] = tt

        _payload = {
            'stats': {
                'total_registered_users': total_registered_users,
                'active_users': active_users_count,
                'pending_registrations': pending_registrations_count,
                'total_tests': total_tests_count,
                'total_tasks': total_global_tasks,
                'unique_tasks_completed': total_global_unique_completed,
                'total_submissions': total_global_submissions,
            },
            'languages': languages_data,
            'tests': tests_data,
            'raters': raters_data,
            'audio_segmentation': audio_seg_data,
            'audio_hours': audio_hours_data,
            'retired_reason_clips': retired_reason_data,
            'audio_seg_artists': _artist_stats_safe(tests, seg_ratings_by_test),
            'task_types': task_types_data,
            'team': _serialize_team(Team.query.get(team_id)) if team_id else None,
            'organization': ORG_NAME,
        }
        _dashboard_cache_write(_payload, team_id)
        _payload['_cache'] = {'hit': False, 'ttl': _DASHBOARD_CACHE_TTL}
        return jsonify(_payload)
        
    except Exception as e:
        app.logger.error(f"Error in admin dashboard endpoint: {e}")
        return jsonify({'error': 'Failed to load admin dashboard statistics.'}), 500


@app.route('/api/rater/tasks', methods=['GET'])
@token_required
def get_assigned_tasks(current_user):
    try:
        token = _require_bearer_token()
        required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        username = required["username"]
        rater = Rater.query.filter_by(name=username).first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404
        
        assigned_ids = []
        if rater.assigned_tasks:
            assigned_ids = [int(x.strip()) for x in rater.assigned_tasks.split(',') if x.strip().isdigit()]
        
        if not assigned_ids:
            return jsonify({'tasks': []}), 200
            
        from sqlalchemy.orm import defer as _defer
        assigned_tests = Test.query.options(_defer(Test.json_entry)).filter(
            Test.id.in_(assigned_ids)).all()
        
        # Sort tests in the order they were assigned
        assigned_tests_dict = {t.id: t for t in assigned_tests}
        sorted_tests = [assigned_tests_dict[tid] for tid in assigned_ids if tid in assigned_tests_dict]

        # Every finished item this annotator has across ALL their assigned batches, in ONE query.
        done_by_test = {}
        for _tid, _page in db.session.query(Rating.test_id, Rating.page_no_progress).filter(
            Rating.rater_id == rater.id,
            Rating.test_id.in_(assigned_ids),
            Rating.completion_status.in_(['completed', 'skipped']),
            Rating.page_no_progress.isnot(None),
        ).distinct().all():
            done_by_test.setdefault(_tid, set()).add(str(_page))
        
        tasks_data = []
        for test in sorted_tests:
            desc = test.description or "No description"
            lang = _infer_language(desc)
            if not lang:
                lang = (test.language_hint or "").capitalize() or "Unknown"

            # Progress: how many of this batch's items this annotator has finished.
            total_count = test.item_count or 0
            completed_count = len(done_by_test.get(test.id, ()))
            if total_count and completed_count > total_count:
                completed_count = total_count
            
            tasks_data.append({
                'id': test.id,
                'description': desc,
                'test_type': test.test_type,
                'language': lang,
                'completed_count': completed_count,
                'total_count': total_count,
                'status': 'Completed' if completed_count == total_count and total_count > 0 else 'In Progress' if completed_count > 0 else 'Not Started'
            })
            
        return jsonify({'tasks': tasks_data}), 200
    except Exception as e:
        app.logger.error(f"Error in get_assigned_tasks: {e}")
        return jsonify({'error': 'Failed to load assigned tasks.'}), 500


@app.route('/api/rater/audio_stats', methods=['GET'])
@token_required
def get_rater_audio_stats(current_user):
    """The signed-in annotator's own audio-segmentation workload, in hours."""
    try:
        token = _require_bearer_token()
        required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        rater = Rater.query.filter_by(name=required["username"]).first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404

        assigned_ids = [int(x.strip()) for x in (rater.assigned_tasks or "").split(',')
                        if x.strip().isdigit()]

        # A batch counts if it is assigned now OR the annotator has already worked on it, so hours never disappear from their own history when a finished batch is.
        worked_ids = [tid for (tid,) in db.session.query(Rating.test_id)
                      .filter(Rating.rater_id == rater.id).distinct().all()]
        candidate_ids = set(assigned_ids) | set(worked_ids)
        if not candidate_ids:
            return jsonify({'enabled': False, 'reason': 'no-audio-tasks'}), 200

        seg_tests = Test.query.filter(
            Test.id.in_(list(candidate_ids)), Test.test_type == 'audio-segmentation'
        ).all()
        if not seg_tests:
            return jsonify({'enabled': False, 'reason': 'no-audio-tasks'}), 200

        seg_test_ids = [t.id for t in seg_tests]
        assigned_set = set(assigned_ids)
        audio_root = _audio_root()

        total = _hours_bucket()
        daily = {}                      # 'YYYY-MM-DD' -> bucket
        batches = []
        last_activity = None

        ratings = Rating.query.filter(
            Rating.rater_id == rater.id, Rating.test_id.in_(seg_test_ids)
        ).all()
        ratings_by_test = {}
        for r in ratings:
            ratings_by_test.setdefault(r.test_id, []).append(r)

        for test in seg_tests:
            dur_by_task = _seg_durations_for_test(test, audio_root)
            batch = _hours_bucket()
            batch_last = None
            for r in ratings_by_test.get(test.id, []):
                if not r.page_no_progress:
                    continue
                secs = dur_by_task.get(str(r.page_no_progress), 0.0)
                if r.completion_status == 'skipped':
                    total['skipped'] += 1
                    batch['skipped'] += 1
                    continue
                if r.completion_status != _SEG_HOURS_STATUS:
                    continue          # drafts ('saved') are not finished work
                total['clips'] += 1
                total['seconds'] += secs
                batch['clips'] += 1
                batch['seconds'] += secs
                day = daily.setdefault(_ist_date_str(r.time_of_submission), _hours_bucket())
                day['clips'] += 1
                day['seconds'] += secs
                if batch_last is None or r.time_of_submission > batch_last:
                    batch_last = r.time_of_submission
                if last_activity is None or r.time_of_submission > last_activity:
                    last_activity = r.time_of_submission

            row = _bucket_summary(batch)
            row.update({
                'test_id': test.id,
                'description': test.description or "No description",
                'total_clips': len(dur_by_task),
                'total_seconds': round(sum(dur_by_task.values()), 1),
                'assigned': test.id in assigned_set,
                'last_activity': batch_last.isoformat() if batch_last else None,
            })
            batches.append(row)

        batches.sort(key=lambda b: (-b['seconds'], b['test_id']))

        today_str = _ist_today_str()
        series = _daily_series(daily, days=30)
        week = _hours_bucket()
        for d in series[:7]:
            week['clips'] += d['clips']
            week['seconds'] += d['seconds']

        # Only the days actually worked, newest first -- the table the annotator reads.
        history = [dict(_bucket_summary(b), date=d) for d, b in daily.items() if b['clips']]
        history.sort(key=lambda x: x['date'], reverse=True)

        active_days = len(history)
        return jsonify({
            'enabled': True,
            'timezone': 'IST (UTC+5:30)',
            'today_date': today_str,
            'total': _bucket_summary(total),
            'today': _bucket_summary(daily.get(today_str) or _hours_bucket()),
            'last_7_days': _bucket_summary(week),
            'daily_series': series,          # dense, zero-filled, newest first
            'daily_history': history,        # only days with work, newest first
            'active_days': active_days,
            'avg_per_active_day': _bucket_summary({
                'clips': round(total['clips'] / active_days) if active_days else 0,
                'seconds': (total['seconds'] / active_days) if active_days else 0.0,
                'skipped': 0,
            }),
            'batches': batches,
            'last_activity': last_activity.isoformat() if last_activity else None,
        }), 200
    except Exception as e:
        app.logger.error(f"Error in get_rater_audio_stats: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load your audio statistics.'}), 500


@app.route('/api/admin/rater/<int:rater_id>/assign_tasks', methods=['POST', 'PUT'])
@token_required
def assign_tasks(current_user, rater_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
        if not _rater_in_scope(current_user, rater):
            return jsonify({'message': 'This annotator is not in your team.'}), 403
        data = request.get_json() or {}
        assigned_tasks = data.get('assigned_tasks', '')
        
        # Clean and validate input: comma-separated digits, de-duplicated, order preserved
        clean_ids = []
        for x in assigned_tasks.split(','):
            x_clean = x.strip()
            if x_clean.isdigit() and x_clean not in clean_ids:
                clean_ids.append(x_clean)

        rater.assigned_tasks = ','.join(clean_ids)
        db.session.commit()
        _dashboard_cache_invalidate()
        return jsonify({'message': 'Tasks assigned successfully', 'assigned_tasks': rater.assigned_tasks}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in assign_tasks: {e}")
        return jsonify({'error': 'Failed to assign tasks.'}), 500


# Admin -> Annotator messaging, nudges, and reversible account deactivation.

def _serialize_message(m):
    return {
        'id': m.id,
        'body': m.body,
        'sender': m.sender,
        'category': m.category or 'message',
        'is_read': bool(m.is_read),
        'created_at': m.created_at.isoformat() if m.created_at else None,
        'edited_at': m.edited_at.isoformat() if getattr(m, 'edited_at', None) else None,
        'broadcast_id': getattr(m, 'broadcast_id', None),
    }


@app.route('/api/admin/rater/<int:rater_id>/message', methods=['POST'])
@token_required
def send_message(current_user, rater_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
        if not _rater_in_scope(current_user, rater):
            return jsonify({'message': 'This annotator is not in your team.'}), 403
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'message': 'Message body cannot be empty.'}), 400
        if len(body) > 2000:
            body = body[:2000]
        category = (data.get('category') or 'message').strip() or 'message'
        msg = Message(rater_id=rater.id, body=body, sender='admin', category=category, is_read=False)
        db.session.add(msg)
        db.session.commit()
        return jsonify({'message': f'Message sent to {rater.name}.', 'data': _serialize_message(msg)}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in send_message: {e}")
        return jsonify({'error': 'Failed to send message.'}), 500


@app.route('/api/admin/message/broadcast', methods=['POST'])
@token_required
def broadcast_message(current_user):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'message': 'Message body cannot be empty.'}), 400
        if len(body) > 2000:
            body = body[:2000]
        # Broadcast to every real annotator (there is no 'admin' Rater row).
        broadcast_id = uuid.uuid4().hex
        recipients = _scoped_raters(_request_team_id(current_user)).all()
        count = 0
        for r in recipients:
            db.session.add(Message(rater_id=r.id, body=body, sender='admin', category='broadcast',
                                   is_read=False, broadcast_id=broadcast_id))
            count += 1
        db.session.commit()
        return jsonify({'message': f'Broadcast sent to {count} annotator(s).', 'count': count,
                        'broadcast_id': broadcast_id}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in broadcast_message: {e}")
        return jsonify({'error': 'Failed to broadcast message.'}), 500


@app.route('/api/admin/messages', methods=['GET'])
@token_required
def get_admin_messages(current_user):
    """Admin outbox: everything the admin has shared."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater_names = {r.id: r.name for r in Rater.query.all()}
        # ?team=<key> narrows the outbox to that team's annotators.
        q = Message.query
        team = _team_by_key(request.args.get('team'))
        if team is not None:
            member_ids = [rid for (rid,) in db.session.query(TeamMember.rater_id)
                          .filter(TeamMember.team_id == team.id).all()]
            q = q.filter(Message.rater_id.in_(member_ids)) if member_ids else q.filter(False)
        msgs = q.order_by(Message.created_at.desc()).all()
        items = []
        broadcasts = {}  # broadcast_id -> aggregate entry (also appended to items)
        for m in msgs:
            if m.broadcast_id:
                entry = broadcasts.get(m.broadcast_id)
                if entry is None:
                    entry = {
                        'kind': 'broadcast',
                        'broadcast_id': m.broadcast_id,
                        'body': m.body,
                        'category': m.category or 'broadcast',
                        'created_at': m.created_at.isoformat() if m.created_at else None,
                        'edited_at': m.edited_at.isoformat() if m.edited_at else None,
                        'recipients_total': 0,
                        'recipients_read': 0,
                        '_sort': m.created_at or datetime.min,
                    }
                    broadcasts[m.broadcast_id] = entry
                    items.append(entry)
                entry['recipients_total'] += 1
                if m.is_read:
                    entry['recipients_read'] += 1
            else:
                items.append({
                    'kind': 'individual',
                    'id': m.id,
                    'rater_id': m.rater_id,
                    'rater_name': rater_names.get(m.rater_id, f'#{m.rater_id}'),
                    'body': m.body,
                    'category': m.category or 'message',
                    'created_at': m.created_at.isoformat() if m.created_at else None,
                    'edited_at': m.edited_at.isoformat() if m.edited_at else None,
                    'is_read': bool(m.is_read),
                    '_sort': m.created_at or datetime.min,
                })
        items.sort(key=lambda x: x['_sort'], reverse=True)
        for x in items:
            x.pop('_sort', None)
        return jsonify({'items': items, 'count': len(items)}), 200
    except Exception as e:
        app.logger.error(f"Error in get_admin_messages: {e}")
        return jsonify({'items': [], 'count': 0}), 500


@app.route('/api/admin/message/<int:message_id>', methods=['PUT'])
@token_required
def edit_message(current_user, message_id):
    """Edit the body of an individual message the admin already sent."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        msg = Message.query.get_or_404(message_id)
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'message': 'Message body cannot be empty.'}), 400
        if len(body) > 2000:
            body = body[:2000]
        now = datetime.utcnow()
        if msg.broadcast_id:
            rows = Message.query.filter_by(broadcast_id=msg.broadcast_id).all()
            for r in rows:
                r.body = body
                r.edited_at = now
            db.session.commit()
            return jsonify({'message': f'Broadcast updated for {len(rows)} annotator(s).',
                            'kind': 'broadcast', 'broadcast_id': msg.broadcast_id}), 200
        msg.body = body
        msg.edited_at = now
        db.session.commit()
        return jsonify({'message': 'Message updated.', 'kind': 'individual',
                        'data': _serialize_message(msg)}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in edit_message: {e}")
        return jsonify({'error': 'Failed to update message.'}), 500


@app.route('/api/admin/broadcast/<broadcast_id>', methods=['PUT'])
@token_required
def edit_broadcast(current_user, broadcast_id):
    """Edit a broadcast (every annotator's copy) in one shot, keyed by the shared broadcast_id."""
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rows = Message.query.filter_by(broadcast_id=broadcast_id).all()
        if not rows:
            return jsonify({'message': 'Broadcast not found.'}), 404
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'message': 'Message body cannot be empty.'}), 400
        if len(body) > 2000:
            body = body[:2000]
        now = datetime.utcnow()
        for r in rows:
            r.body = body
            r.edited_at = now
        db.session.commit()
        return jsonify({'message': f'Broadcast updated for {len(rows)} annotator(s).',
                        'count': len(rows)}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in edit_broadcast: {e}")
        return jsonify({'error': 'Failed to update broadcast.'}), 500


@app.route('/api/admin/rater/<int:rater_id>/nudge', methods=['POST'])
@token_required
def nudge_rater(current_user, rater_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
        if not _rater_in_scope(current_user, rater):
            return jsonify({'message': 'This annotator is not in your team.'}), 403
        data = request.get_json() or {}
        note = (data.get('note') or '').strip()
        body = ("Reminder: you have annotation tasks assigned and waiting. Please "
                "continue when you can — thank you!")
        if note:
            body += f"\n\nNote from admin: {note}"
        msg = Message(rater_id=rater.id, body=body, sender='admin', category='nudge', is_read=False)
        db.session.add(msg)
        db.session.commit()
        return jsonify({'message': f'Nudge sent to {rater.name}.', 'data': _serialize_message(msg)}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in nudge_rater: {e}")
        return jsonify({'error': 'Failed to send nudge.'}), 500


@app.route('/api/admin/rater/<int:rater_id>/deactivate', methods=['POST'])
@token_required
def deactivate_rater(current_user, rater_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    rater = Rater.query.get(rater_id)
    if rater is None:
        return jsonify({'message': 'Annotator not found.'}), 404
    try:
        if not _rater_in_scope(current_user, rater):
            return jsonify({'message': 'This annotator is not in your team.'}), 403
        data = request.get_json() or {}
        confirm = (data.get('confirm') or '').strip().lower()
        # Require the admin to type exactly: deactivate <name>. (The retired "delete <name>" phrase is still accepted so an old cached client keeps working.)
        if confirm not in (f"deactivate {rater.name}".strip().lower(),
                           f"delete {rater.name}".strip().lower()):
            return jsonify({'message': f'Confirmation text did not match. Type "deactivate {rater.name}" to confirm.'}), 400

        # Reversible: stash the current assignment, then unlock those tasks.
        if rater.assigned_tasks:
            rater.prev_assigned_tasks = rater.assigned_tasks
        rater.assigned_tasks = ''
        rater.is_active = False
        db.session.commit()
        _dashboard_cache_invalidate()
        return jsonify({
            'message': f'{rater.name} has been deactivated. Their {len((rater.prev_assigned_tasks or "").split(",")) if rater.prev_assigned_tasks else 0} task(s) were unlocked. Annotations were kept.',
            'account_active': False
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in deactivate_rater: {e}")
        return jsonify({'error': 'Failed to deactivate annotator.'}), 500


@app.route('/api/admin/rater/<int:rater_id>/reactivate', methods=['POST'])
@token_required
def reactivate_rater(current_user, rater_id):
    if not _is_admin(current_user):
        return jsonify({'message': 'Unauthorized'}), 401
    rater = Rater.query.get(rater_id)
    if rater is None:
        return jsonify({'message': 'Annotator not found.'}), 404
    try:
        if not _rater_in_scope(current_user, rater):
            return jsonify({'message': 'This annotator is not in your team.'}), 403
        rater.is_active = True
        # Restore the previous assignment only if nothing has been assigned since.
        if not rater.assigned_tasks and rater.prev_assigned_tasks:
            rater.assigned_tasks = rater.prev_assigned_tasks
        rater.prev_assigned_tasks = ''
        db.session.commit()
        _dashboard_cache_invalidate()
        return jsonify({
            'message': f'{rater.name} has been reactivated.',
            'account_active': True,
            'assigned_tasks': rater.assigned_tasks or ''
        }), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in reactivate_rater: {e}")
        return jsonify({'error': 'Failed to reactivate annotator.'}), 500


@app.route('/api/rater/messages', methods=['GET'])
@token_required
def get_rater_messages(current_user):
    # Admin has no inbox; annotators fetch their own messages.
    if _is_admin(current_user):
        return jsonify({'messages': [], 'unread_count': 0}), 200
    try:
        rater = Rater.query.filter_by(name=current_user).first()
        if not rater:
            return jsonify({'messages': [], 'unread_count': 0}), 200
        msgs = (Message.query.filter_by(rater_id=rater.id)
                .order_by(Message.created_at.desc()).limit(100).all())
        unread = sum(1 for m in msgs if not m.is_read)
        return jsonify({
            'messages': [_serialize_message(m) for m in msgs],
            'unread_count': unread
        }), 200
    except Exception as e:
        app.logger.error(f"Error in get_rater_messages: {e}")
        return jsonify({'messages': [], 'unread_count': 0}), 200


@app.route('/api/rater/messages/read', methods=['POST'])
@token_required
def mark_messages_read(current_user):
    if _is_admin(current_user):
        return jsonify({'message': 'No inbox for admin.'}), 200
    try:
        rater = Rater.query.filter_by(name=current_user).first()
        if not rater:
            return jsonify({'message': 'Rater not found.'}), 404
        data = request.get_json(silent=True) or {}
        ids = data.get('ids')
        q = Message.query.filter_by(rater_id=rater.id, is_read=False)
        if isinstance(ids, list) and ids:
            q = q.filter(Message.id.in_([i for i in ids if isinstance(i, int)]))
        updated = 0
        for m in q.all():
            m.is_read = True
            updated += 1
        db.session.commit()
        return jsonify({'message': 'Marked as read.', 'updated': updated}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in mark_messages_read: {e}")
        return jsonify({'error': 'Failed to mark messages read.'}), 500


# Team / pool endpoints.
from application import team_api  # noqa: E402,F401
from application import pool_api  # noqa: E402,F401
from application import pool_tasks  # noqa: E402,F401
from application import password_reset  # noqa: E402,F401
from application import storage_api  # noqa: E402,F401
from application import mdfs_scores  # noqa: E402,F401
