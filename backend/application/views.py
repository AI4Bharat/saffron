from flask import jsonify, request
from werkzeug.security import generate_password_hash
from flask import current_app as app
from application.models import db, Rater, Test, Rating, Study, Session, Consent, Message
from datetime import datetime, timedelta
import jwt
import uuid
from functools import wraps
import random
import logging
from logging.handlers import RotatingFileHandler
from flask_caching import Cache

random.seed(42)

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


# Duration of the audio_segmentation WAV files, cached per (path, mtime) so the
# headers are only read once per file per worker.
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

# Set up logging
if not app.debug:
    handler = RotatingFileHandler('error.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.ERROR)
    app.logger.addHandler(handler)


@app.errorhandler(Exception)
def unhandled_exception(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        # Return the error as JSON (never Werkzeug's HTML page) so the SPA can
        # always parse a `message`. `description` carries the specific reason
        # (e.g. the abort() text below); `error` is the HTTP status name.
        payload = {
            'message': e.description or e.name,
            'error': e.name,
            'status': e.code,
        }
        return jsonify(payload), e.code
    # exc_info=True records the full traceback in error.log for real debugging,
    # while the client only ever sees a generic message (no internals leaked).
    app.logger.error('Unhandled Exception: %s', e, exc_info=True)
    return jsonify({'message': 'Something went wrong on our end. Please try again.',
                    'error': 'Internal Server Error', 'status': 500}), 500


def _require_bearer_token():
    """Return the bearer token from the Authorization header, or abort(401) with a
    clear JSON message. Replaces the old ``.split()[1]`` pattern that raised an
    opaque 500 when the header was missing or malformed."""
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
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401
        try:
            token = token.split()[1]
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user = data['username']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
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
    audio_dir = os.path.join(base_dir, 'audio_segmentation')
    filepath = os.path.join(audio_dir, filename)
    
    if not os.path.exists(filepath):
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


# =====================
# CRUD Rater 
# =====================


def generate_token(username):
    payload = {
        'username': username,
        # 'language': language,
        # 'speakers': speakers,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm='HS256')


@app.route('/api/login', methods=['POST'])
def login():
    import os
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = Rater.query.filter_by(name=username).first()
    if user and user.password == password:
        # Deactivated annotators cannot log in (reversible via admin reactivate).
        if getattr(user, 'is_active', True) is False:
            return jsonify({'message': 'This account has been deactivated. Please contact the admin.'}), 403
        auth_token = generate_token(username)
        return jsonify({'token': auth_token}), 200
    elif username == 'admin':
        admin_pass = os.getenv('ADMIN_PASSWORD', 'admin')
        if password == admin_pass:
            auth_token = generate_token('admin')
            return jsonify({'token': auth_token}), 200
        else:
            return jsonify({'message': 'Invalid username or password'}), 401
    else:
        return jsonify({'message': 'Invalid username or password'}), 401


# ---------------------------------------------------------------------------
# Daily signup PIN
# ---------------------------------------------------------------------------
# New annotators must enter an 8-digit PIN that the admin shares. The PIN rotates
# once per day and is stored in backend/signup_key.txt as "YYYY-MM-DD PIN".
import os  # noqa: E402  (views.py imports os further down; needed at module level here)

# Public base URL used to build deep links into a specific task (see TestView ?task=).
_SAFFRON_BASE_URL = os.environ.get('SAFFRON_BASE_URL', 'https://tts-saffron.ai4bharat.org')

SIGNUP_KEY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'signup_key.txt'
)


def _daily_signup_pin():
    """Return today's 8-digit PIN, generating + persisting a new one if the stored
    PIN is from a previous day (or the file is missing/corrupt).

    Concurrency: the whole read-check-write runs under an exclusive lock on the key
    file, so with N gunicorn workers only one can ever be minting a PIN. Any worker
    that arrives during a rotation blocks on the lock, then re-reads and returns the
    PIN the winner just wrote -- two workers can never hand out different PINs for
    the same day, not even on the midnight boundary.
    """
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
    if current_user != "admin":
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

    # Add the new user to the database
    try:
        db.session.add(new_user)
        db.session.commit()  # Commit to save the user in the database
    except Exception as e:
        db.session.rollback()  # In case of error, rollback the transaction
        return jsonify({'message': 'Error occurred while signing up. Please try again.',
                        'error': e}), 500

    # Generate an authentication token for the new user
    auth_token = generate_token(name)

    # Return the token in the response
    return jsonify({'token': auth_token}), 201  # 201 status code for successful resource creation

# =====================
# CRUD Tests via Login
# =====================
@app.route('/api/test/<int:test_id>', methods=['GET'])
@token_required
def get_test(current_user, test_id):
    token = _require_bearer_token()
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    username = required["username"]
    rater = Rater.query.filter_by(name=username).first()
    if not rater:
        if username == "admin":
            rater = Rater.query.first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404
    rater_id = rater.id
    test = Test.query.filter_by(id=test_id).first_or_404()

    # Task assignment locking protection.
    # A task assigned to THIS rater is always accessible to them; a task assigned to
    # someone else is locked; a task assigned to nobody stays open (legacy behaviour).
    my_assigned_ids = []
    if username != "admin":
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
    # Admin uses 'Direct Task Preview' to inspect the pristine annotation
    # flow, so it must NEVER load another annotator's saved work (admin has
    # no Rater row and only borrows Rater.query.first() for auth above).
    if username == "admin":
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
    # OFF (default): open task — every annotator sees every item, nothing hidden, so
    # a task can intentionally be annotated by multiple annotators. ON: when this task
    # is ASSIGNED to the current rater, hide items ANOTHER annotator already COMPLETED,
    # so a batch can be handed over mid-way (A did 1-100 -> B sees only 101-N). Skips
    # are NOT hidden (still open work). Order is ALWAYS the original json_entry order.
    others_completed_ids = set()
    if username != "admin" and test_id in my_assigned_ids and bool(getattr(test, 'handoff_mode', False)):
        for r in Rating.query.filter(
            Rating.test_id == test_id,
            Rating.rater_id != rater_id,
            Rating.completion_status == 'completed'
        ).all():
            if r.page_no_progress:
                others_completed_ids.add(str(r.page_no_progress))

    # ALWAYS preserve the original json_entry order (no done-first shuffling) so the
    # task list looks identical on every visit. Items completed by OTHER annotators
    # (the handoff case above) are dropped from this rater's view.
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
        # Performance optimization: shallow copy dictionary and copy nested dialogue lists to avoid copy.deepcopy
        sample_copy = {k: v for k, v in sample.items()}
        for k in ['dialogue', 'conversation', 'turns']:
            if k in sample_copy and isinstance(sample_copy[k], list):
                sample_copy[k] = [dict(turn) for turn in sample_copy[k]]
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
                # Benchmark verification: reload the annotator's edited raw_text /
                # spoken_form and their accept/reject decision so a saved draft or a
                # completed item re-opens exactly as they left it.
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

    # Resume at the first item THIS rater hasn't finished (in original order). If
    # everything is done, point past the end so the frontend shows the complete state.
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
def _rollback_failed_session(exc=None):
    # main.py keeps one app context pushed forever, so Flask-SQLAlchemy never
    # removes the scoped session between requests. If a flush failed and the
    # view swallowed it, the session stays unusable for every later request on
    # this worker. Roll it back here so one bad request can't poison the rest.
    try:
        if exc is not None or not db.session.is_active:
            db.session.rollback()
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
            if required["username"] == "admin":
                rater = Rater.query.first()
            if not rater:
                return jsonify({'message': 'Rater not found'}), 404
        data = request.get_json()

        # Task assignment locking protection (a rater may always submit to their own assigned task)
        username = required["username"]
        test_id = data.get('test_id')
        if test_id and username != "admin":
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

        existing_rating = Rating.query.filter_by(
            rater_id=rater.id,
            test_id=data['test_id'],
            page_no_progress=data.get('pageNo_progress')
        ).first()

        if existing_rating:
            existing_rating.results_json = data['results_json']
            existing_rating.time_taken_to_submit = data['time_taken_to_submit']
            existing_rating.completion_status = completion_status
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
                completion_status=completion_status
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
def update_rating(rating_id):
    data = request.get_json()
    rating = Rating.query.get_or_404(rating_id)
    if 'results_json' in data:
        rating.results_json = data['results_json']
    if 'time_taken_to_submit' in data:
        rating.time_taken_to_submit = data['time_taken_to_submit']
    if 'page_no_progress' in data:
        rating.page_no_progress = data['page_no_progress']
    db.session.commit()
    return jsonify({'message': 'Rating updated successfully'})


# =======================
# CRUD Tests via Prolific
# =======================


@app.route('/api/prolific/study', methods=['POST'])
def create_study():
    """
    Create a new study and link it to a test.
    Example Request Body:
    {
        "study_id": "675f98c80c6433c976165f3e",
        "test_id": 123,
        "completion_url": "https://app.prolific.com/submissions/complete?cc=COGEJ6Y9"
    }
    """
    data = request.get_json()
    study_id = data.get('study_id')
    test_id = data.get('test_id')
    completion_url = data.get('completion_url')

    if not study_id or not test_id or not completion_url:
        return jsonify({'message': 'Missing required fields'}), 400

    test = Test.query.get(test_id)
    if not test:
        return jsonify({'message': 'Test not found'}), 404

    # Check if study already exists
    existing_study = Study.query.filter_by(study_id=str(study_id)).first()
    if existing_study:
        return jsonify({'message': 'Study already exists'}), 400

    new_study = Study(
        study_id=study_id,
        test_id=test_id,
        completion_url=completion_url
    )

    try:
        db.session.add(new_study)
        db.session.commit()
        return jsonify({'message': 'Study created successfully',
                        'study_id': study_id}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error('Error creating study: %s', e)
        print(e)
        return jsonify({'message': 'Error creating study'}), 500


@app.route('/api/prolific/session', methods=['POST'])
def create_session():
    """
    Create a new session when a Prolific user accesses the test URL.
    Request Query Parameters:
    - PROLIFIC_PID
    - STUDY_ID
    - SESSION_ID
    """
    prolific_pid = request.args.get('PROLIFIC_PID')
    study_id = request.args.get('STUDY_ID')
    session_id = request.args.get('SESSION_ID')

    if not prolific_pid or not study_id or not session_id:
        return jsonify({'message': 'Missing required query parameters'}), 400

    # Check if the study exists
    study = Study.query.filter_by(study_id=str(study_id)).first()
    if not study:
        return jsonify({'message': 'Study not found'}), 404

    # Check if the session already exists
    existing_session = Session.query.filter_by(session_id=session_id).first()
    if existing_session:
        return jsonify({'message': 'Session already exists'}), 400

    new_session = Session(
        session_id=session_id,
        study_id=study.id,
        prolific_pid=prolific_pid
    )

    try:
        db.session.add(new_session)
        db.session.commit()
        return jsonify({'message': 'Session created successfully', 'session_id': session_id}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error('Error creating session: %s', e)
        return jsonify({'message': 'Error creating session'}), 500


@app.route('/api/prolific/study', methods=['GET'])
def get_test_for_prolific_user():
    """
    Serve the test to a Prolific user without requiring login.
    Query Parameters:
    - PROLIFIC_PID: Prolific participant ID
    - STUDY_ID: Prolific study ID
    - SESSION_ID: Prolific session ID
    """
    prolific_pid = request.args.get('PROLIFIC_PID')
    study_id = request.args.get('STUDY_ID')
    session_id = request.args.get('SESSION_ID')

    if not prolific_pid:
        return jsonify({'message': 'Missing required parameter: PROLIFIC_PID'}), 400
    if not study_id:
        return jsonify({'message': 'Missing required parameter: STUDY_ID'}), 400
    if not session_id:
        return jsonify({'message': 'Missing required parameter: SESSION_ID'}), 400
    
    # Step 1: Check if a rater exists for the Prolific ID, create one if not
    rater = Rater.query.filter_by(email=prolific_pid).first()
    if not rater:
        # Generate a random password
        random_password = generate_password_hash(
            f"{prolific_pid}_{study_id}",
            # method='pbkdf2:sha256'
        )
        rater = Rater(
            name=f"Prolific_{prolific_pid}",
            age=0,  # Default age as it's not collected
            gender="Unknown",  # Default gender
            email=prolific_pid,  # Using Prolific PID as email
            password=random_password
        )

        db.session.add(rater)
        db.session.commit()

    
    # Step 2: Get the test ID associated with the study
    study = Study.query.filter_by(study_id=study_id).first()
    if not study:
        return jsonify({'message': 'Study not found'}), 404

    test = Test.query.get(study.test_id)
    if not test:
        return jsonify({'message': 'Test not found'}), 404

    # Step 3: Check if a session exists for the Prolific user, create one if not
    session = Session.query.filter_by(session_id=session_id).first()
    if not session:
        session = Session(
            session_id=session_id,
            study_id=study.id,
            prolific_pid=prolific_pid
        )
        
        db.session.add(session)
        db.session.commit()



    # Step 4: Query the Rating table to get page numbers already completed
    ratings = Rating.query.filter_by(
        rater_id=rater.id, test_id=test.id
    ).all()
    
    latest_status = {}
    for r in ratings:
        if r.page_no_progress:
            pid = str(r.page_no_progress)
            if pid not in latest_status or r.time_of_submission > latest_status[pid]['time']:
                latest_status[pid] = {
                    'status': r.completion_status or 'completed',
                    'time': r.time_of_submission
                }
    
    completed_pages_raw = {pid for pid, val in latest_status.items() if val['status'] in ['completed', 'skipped']}

    # Get all pages in the test
    all_pages = [entry['id'] for entry in test.json_entry]

    # Filter out completed pages and shuffle the remaining ones deterministically per user
    completed_pages = {page for page in all_pages if str(page) in completed_pages_raw}
    remaining_pages = [page for page in all_pages if page not in completed_pages]
    
    user_seed = f"saffron_{rater.id}_{test.id}"
    user_random = random.Random(user_seed)
    user_random.shuffle(remaining_pages)

    # Create a dictionary for quick lookup of entries by ID
    entry_dict = {entry['id']: entry for entry in test.json_entry}

    # Combine completed pages (preserving their order) with shuffled remaining pages
    shuffled_sequence = [entry_dict[page_id] for page_id in completed_pages] + \
                        [entry_dict[page_id] for page_id in remaining_pages]
                        
    # Map latest ratings by task ID to merge corrections
    latest_ratings = {}
    for r in ratings:
        if r.page_no_progress:
            pid = str(r.page_no_progress)
            if pid not in latest_ratings or r.time_of_submission > latest_ratings[pid].time_of_submission:
                latest_ratings[pid] = r

    full_test_sequence = []
    for sample in shuffled_sequence:
        # Performance optimization: shallow copy dictionary and copy nested dialogue lists to avoid copy.deepcopy
        sample_copy = {k: v for k, v in sample.items()}
        for k in ['dialogue', 'conversation', 'turns']:
            if k in sample_copy and isinstance(sample_copy[k], list):
                sample_copy[k] = [dict(turn) for turn in sample_copy[k]]
        
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
                # Benchmark verification: reload the annotator's edited raw_text /
                # spoken_form and their accept/reject decision so a saved draft or a
                # completed item re-opens exactly as they left it.
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
        full_test_sequence.append(sample_copy)

    auth_token = generate_token(rater.name)

    # Step 5: Check if the user has given consent for the test
    consent = Consent.query.filter_by(rater_id=rater.id, test_id=test.id).first()
    if consent:
        consent_status = True
    else:
        consent_status = False

    remaining_time = get_remaining_time(rater.id, study.id)

    # Step 6: Serve the test
    return jsonify({
        'test_id': test.id,
        'test_type': test.test_type,
        'description': test.description,
        'json_entry': full_test_sequence,
        'page_no': len(completed_pages),
        'completion_url': study.completion_url,
        'token': auth_token,
        'consent': consent_status,
        'rejection_url': "https://app.prolific.com/submissions/complete?cc=C8S11MVG",
        'remaining_time': remaining_time
    })

# add a new point to give consent
@app.route('/api/prolific/consent/<int:test_id>', methods=['GET'])
def give_consent(test_id):
    token = _require_bearer_token()
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    rater = Rater.query.filter_by(name=required["username"]).first_or_404()
    test = Test.query.filter_by(id=test_id).first_or_404()
    if rater is None or test is None:
        return jsonify({'message': 'Rater or Test not found'}), 404
    consent = Consent(
        rater_id=rater.id,
        test_id=test_id
    )
    db.session.add(consent)
    db.session.commit()

    return jsonify({'message': 'Consent given successfully'}), 201

@app.route('/api/prolific/rating', methods=['POST'])
def save_rating():
    """
    Save the ratings submitted by Prolific users.
    Request Body:
    {
        "session_id": "session_id",
        "test_id": 123,
        "results_json": {...},
        "time_taken_to_submit": 300,
        "completion_status": "completed"
    }
    """
    data = request.get_json()
    session_id = data.get('session_id')
    test_id = data.get('test_id')
    results_json = data.get('results_json')
    time_taken_to_submit = data.get('time_taken_to_submit')
    completion_status = data.get('completion_status', 'completed')

    if not session_id or not test_id or not results_json or not time_taken_to_submit:
        return jsonify({'message': 'Missing required fields'}), 400

    session = Session.query.filter_by(session_id=session_id).first()
    if not session:
        return jsonify({'message': 'Session not found'}), 404

    rater = Rater.query.filter_by(email=session.prolific_pid).first()

    # Append additional fields to results_json
    if not isinstance(results_json, dict):
        return jsonify({'message': 'Invalid results_json format'}), 400

    results_json.update({
        'session_id': session_id,
        'prolific_id': session.prolific_pid,
        'study_id': session.study_id,
        'test_id': test_id,
        'time': datetime.now().isoformat(),  # Current timestamp
        'time_taken': time_taken_to_submit / 1000,  # Convert to seconds
        'data_id': data.get('pageNo_progress')  # Optional field
    })

    new_rating = Rating(
        rater_id=rater.id,  # Prolific users are anonymous, no Rater ID
        test_id=test_id,
        results_json=results_json,
        time_taken_to_submit=time_taken_to_submit,
        page_no_progress=data.get('pageNo_progress'),
        completion_status=completion_status
    )

    try:
        db.session.add(new_rating)
        db.session.commit()
        return jsonify({'message': 'Rating created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        app.logger.error('Error saving rating: %s', e)
        return jsonify({'message': 'Error saving rating'}), 500

# =======================
# CRUD Basic 
# =======================
@app.route('/api/test', methods=['POST'])
def create_test():
    """
    Create a new test.
    Example Request Body:
    {
        "test_type": "Multiple Choice",
        "description": "A test for evaluating multiple-choice questions.",
        "json_entry": [
            {"id": 1, "question": "What is 2+2?", "options": ["3", "4", "5"], "answer": "4"},
            {"id": 2, "question": "What is the capital of France?", "options": ["Paris", "London", "Berlin"], "answer": "Paris"}
        ]
    }
    """
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
    """
    Get the contents of the database.
    """
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
        if username == "admin":
            rater = Rater.query.first()
        if not rater:
            return jsonify({'message': 'Rater not found'}), 404
    
    test = Test.query.filter_by(id=test_id).first_or_404()

    # Task assignment locking protection (a rater may always access their own assigned task)
    if username != "admin":
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

    if not token or required["username"] != "admin":
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
                # Ratings can outlive their Test (e.g. a test was deleted). Skip
                # those orphans instead of crashing the whole endpoint on None.id.
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
    if current_user != "admin":
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
                r.time_taken_to_submit
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
        return {'artists': [], 'overall': {}}


@app.route('/api/admin/rater_activity', methods=['GET'])
@token_required
def rater_activity(current_user):
    """Per-annotator work done inside a date window (default: all time).

    ?from=YYYY-MM-DD&to=YYYY-MM-DD  (both inclusive; either may be omitted)
    Counts DISTINCT completed/skipped task ids, submissions and time spent, so the
    admin can see "what did this person do last week" instead of only lifetime totals.
    """
    if current_user != "admin":
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

    q = Rating.query.options(defer(Rating.results_json))
    if d_from:
        q = q.filter(Rating.time_of_submission >= d_from)
    if d_to:
        q = q.filter(Rating.time_of_submission < d_to + _td(days=1))   # inclusive end day
    ratings = q.all()

    per = {}
    for r in ratings:
        p = per.setdefault(r.rater_id, {'tasks': set(), 'submissions': 0, 'secs': 0.0, 'last': None})
        p['submissions'] += 1
        if r.page_no_progress and r.completion_status in ('completed', 'skipped'):
            p['tasks'].add(str(r.page_no_progress))
        if r.time_taken_to_submit:
            secs = r.time_taken_to_submit / 1000.0
            if 0 < secs < 7200:          # ignore tab-left-open outliers
                p['secs'] += secs
        if r.time_of_submission and (p['last'] is None or r.time_of_submission > p['last']):
            p['last'] = r.time_of_submission

    raters = {x.id: x for x in Rater.query.all()}
    rows = []
    for rid, p in per.items():
        rt = raters.get(rid)
        rows.append({
            'rater_id': rid,
            'name': rt.name if rt else f'Rater {rid}',
            'email': rt.email if rt else '',
            'completed_tasks': len(p['tasks']),
            'submissions': p['submissions'],
            'hours': round(p['secs'] / 3600.0, 2),
            'avg_seconds': round(p['secs'] / p['submissions'], 1) if p['submissions'] else 0,
            'last_active': p['last'].isoformat() if p['last'] else None,
        })
    rows.sort(key=lambda x: -x['completed_tasks'])
    return jsonify({
        'from': request.args.get('from') or None,
        'to': request.args.get('to') or None,
        'raters': rows,
        'totals': {
            'completed_tasks': sum(r['completed_tasks'] for r in rows),
            'submissions': sum(r['submissions'] for r in rows),
            'hours': round(sum(r['hours'] for r in rows), 2),
            'active_raters': len(rows),
        }
    }), 200


@app.route('/api/admin/export_tasks_csv', methods=['GET'])
@token_required
def export_tasks_csv(current_user):
    """CSV of tests: Sr. No. (per language), Language, Task ID, Detail, No. of Task.

    Query params: ?version=6|new|base (optional), ?test_type=conversation-editable (optional)
    """
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response

    version = request.args.get('version') or None
    test_type = request.args.get('test_type') or None
    tests = Test.query.order_by(Test.id).all()
    csv_text = admin_reports.tasks_export_csv(tests, test_type=test_type, version=version)
    fname = "tasks_export"
    if test_type:
        fname += f"_{test_type}"
    if version:
        fname += f"_v{version}"
    return Response(
        csv_text, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_audio_clips_csv', methods=['GET'])
@token_required
def export_audio_clips_csv(current_user):
    """Clip-level audio-segmentation export with a playable Saffron deep link per clip.

    ?all=1 includes accepted clips too (default: rejected only).
    """
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response

    # Default: EVERY reviewed clip gets a link. ?rejected_only=1 narrows it.
    only_rejected = request.args.get('rejected_only') in ('1', 'true', 'yes')
    tests = Test.query.filter_by(test_type='audio-segmentation').all()
    seg_ids = [t.id for t in tests]
    ratings_by_test = {}
    for r in Rating.query.filter(Rating.test_id.in_(seg_ids)).all():
        ratings_by_test.setdefault(r.test_id, []).append(r)
    csv_text = admin_reports.audio_clips_csv(tests, ratings_by_test, only_rejected=only_rejected)
    name = 'audio_clips_rejected.csv' if only_rejected else 'audio_clips_all.csv'
    return Response(csv_text, mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename={name}'})


@app.route('/api/admin/export_artist_report_csv', methods=['GET'])
@token_required
def export_artist_report_csv(current_user):
    """Vendor-shareable CSV: per-artist rejection rates + reason breakdown."""
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    import admin_reports
    from flask import Response

    tests = Test.query.filter_by(test_type='audio-segmentation').all()
    seg_ids = [t.id for t in tests]
    ratings_by_test = {}
    for r in Rating.query.filter(Rating.test_id.in_(seg_ids)).all():
        ratings_by_test.setdefault(r.test_id, []).append(r)
    stats = admin_reports.artist_rejection_stats(tests, ratings_by_test)
    return Response(
        admin_reports.artist_report_csv(stats), mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=artist_rejection_report.csv'}
    )


@app.route('/api/admin/export_annotators_csv', methods=['GET'])
@token_required
def export_annotators_csv(current_user):
    """CSV export summarizing annotator work: current pending task ID, working on task ID,
    no. of tasks done, assigned batches, submissions, hours spent, and status.

    Optional params: ?from=YYYY-MM-DD&to=YYYY-MM-DD
    """
    if current_user != "admin":
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

    raters = Rater.query.all()
    tests = Test.query.all()
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
        csv_text, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_rater_ratings_csv/<int:rater_id>', methods=['GET'])
@token_required
def export_rater_ratings_csv(current_user, rater_id):
    """Detailed line-by-line CSV of all ratings submitted by a specific rater within optional date bounds."""
    if current_user != "admin":
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

    tests = Test.query.all()
    csv_text = admin_reports.rater_detailed_ratings_csv(rater, tests, ratings)

    r_name = rater.name.replace(' ', '_')
    fname = f"annotations_rater_{rater_id}_{r_name}"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        csv_text, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )


@app.route('/api/admin/export_all_ratings_csv', methods=['GET'])
@token_required
def export_all_ratings_csv(current_user):
    """Detailed line-by-line CSV of all ratings submitted across all raters within optional date bounds."""
    if current_user != "admin":
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

    raters = Rater.query.all()
    tests = Test.query.all()
    csv_text = admin_reports.all_detailed_ratings_csv(raters, tests, ratings)

    fname = "all_annotations_report"
    if request.args.get('from'):
        fname += f"_from_{request.args.get('from')}"
    if request.args.get('to'):
        fname += f"_to_{request.args.get('to')}"

    return Response(
        csv_text, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={fname}.csv'}
    )





import json as _json_mod  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402
json = _json_mod

# Dashboard payload cache (shared across gunicorn workers via a temp file).
_DASHBOARD_CACHE = os.path.join(tempfile.gettempdir(), 'saffron_dashboard_cache.json')
_DASHBOARD_CACHE_TTL = int(os.environ.get('DASHBOARD_CACHE_TTL', '60'))


def _dashboard_cache_read():
    """Return (payload, age_seconds) if a fresh cache exists, else (None, None)."""
    try:
        age = time.time() - os.path.getmtime(_DASHBOARD_CACHE)
        if age > _DASHBOARD_CACHE_TTL:
            return None, None
        with open(_DASHBOARD_CACHE, encoding='utf-8') as fh:
            return json.load(fh), age
    except Exception:
        return None, None


def _dashboard_cache_write(payload):
    try:
        tmp = _DASHBOARD_CACHE + f'.{os.getpid()}.tmp'
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(payload, fh)
        os.replace(tmp, _DASHBOARD_CACHE)   # atomic; concurrent workers can't tear it
    except Exception as e:
        print(f"[WARN] dashboard cache write failed: {e}")


@app.route('/api/admin/task/<int:test_id>/annotations', methods=['GET'])
@token_required
def get_task_annotations(current_user, test_id):
    """Admin-only: the submitted annotations for one task, grouped by annotator.

    Powers the admin "review" view that opens when a task is clicked in the Tasks
    Overview: instead of the blank annotation page, the admin sees what each
    annotator actually submitted. When several annotators worked the same task they
    each get their own tab. Read-only -- never writes to any table.
    """
    if current_user != "admin":
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
        """Normalize an accept/reject decision across task types (benchmark uses
        'decision', conversation/audio use 'evaluation')."""
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
    """Admin-only: toggle a task's handoff mode.

    enabled=false (default) -> OPEN: multiple annotators may each annotate every item.
    enabled=true            -> HANDOFF: an assignee stops seeing items another annotator
                               already completed, so leftover work can be handed off.
    Only flips the boolean flag; never touches Rating/annotation data.
    """
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    test = Test.query.filter_by(id=test_id).first_or_404()
    data = request.get_json() or {}
    test.handoff_mode = bool(data.get('enabled'))
    db.session.commit()
    return jsonify({'test_id': test.id, 'handoff_mode': bool(test.handoff_mode)}), 200


@app.route('/api/admin/dashboard', methods=['GET'])
@token_required
def get_admin_dashboard(current_user):
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401

    if request.args.get('refresh') not in ('1', 'true', 'yes'):
        _cached, _age = _dashboard_cache_read()
        if _cached is not None:
            _cached['_cache'] = {'hit': True, 'age_seconds': round(_age, 1),
                                 'ttl': _DASHBOARD_CACHE_TTL}
            return jsonify(_cached)

    try:
        from sqlalchemy.orm import defer
        import re

        # 1. Fetch all raters and all ratings once to avoid N+1 queries
        raters = Rater.query.all()
        total_registered_users = len(raters)
        
        # results_json is a large JSON blob and is only needed for the audio-segmentation
        # rollups below; deferring it here takes this query from ~2.9s to ~0.6s.
        all_ratings = Rating.query.options(defer(Rating.results_json)).all()

        # Only the "evaluation" field of results_json is needed for the per-batch
        # accept/reject tallies. Pull it straight out in SQL so the deferred blob is
        # never lazy-loaded (loading all 42k blobs costs ~2.9s; this costs ~0.6s).
        eval_by_rating = {}
        try:
            from sqlalchemy import func as _sqlfunc
            for _rid, _ev in db.session.query(
                Rating.id, _sqlfunc.json_extract(Rating.results_json, '$.evaluation')
            ).all():
                if _ev:
                    eval_by_rating[_rid] = str(_ev).strip().lower()
        except Exception as _e:
            print(f"[WARN] json_extract(evaluation) failed, falling back to blobs: {_e}")
            eval_by_rating = None
        
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
            completed_tasks_count = len({r.page_no_progress for r in rater_ratings if r.page_no_progress and r.completion_status in ['completed', 'skipped']})
            
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
        
        # 2. Test batches metrics (Defer the heavy json_entry column to avoid loading/deserializing 120MB)
        tests = Test.query.options(defer(Test.json_entry)).all()
        total_tests_count = len(tests)
        
        languages_list = ["hindi", "bengali", "gujarati", "kannada", "malayalam", "marathi", "odia", "tamil", "telugu", "urdu", "english"]
        
        tests_data = []
        languages_map = {}
        
        total_global_tasks = 0
        total_global_unique_completed = 0
        total_global_submissions = 0
        
        for test in tests:
            desc = test.description or "No description"
            
            # Infer language from description first (very fast)
            lang = ""
            desc_lower = desc.lower()
            for l in languages_list:
                if l in desc_lower:
                    lang = l.capitalize()
                    break
                    
            if not lang:
                # Fallback to json_entry only if not in description (unlikely)
                if test.json_entry and isinstance(test.json_entry, list) and len(test.json_entry) > 0:
                    first_item = test.json_entry[0]
                    lang = first_item.get('target_language') or first_item.get('language') or first_item.get('metadata', {}).get('language') or ""
                    lang = lang.capitalize() if lang else "Unknown"
                else:
                    lang = "Unknown"
            
            # Parse total tasks count from description if available (Tasks X to Y)
            total_tasks = 0
            match = re.search(r"Tasks (\d+) to (\d+)", desc)
            if match:
                total_tasks = int(match.group(2)) - int(match.group(1)) + 1
            else:
                total_tasks = len(test.json_entry) if test.json_entry else 0
                
            test_ratings = ratings_by_test.get(test.id, [])
            unique_completed = len({r.page_no_progress for r in test_ratings if r.page_no_progress and r.completion_status in ['completed', 'skipped']})
            total_submissions = len([r for r in test_ratings if r.completion_status in ['completed', 'skipped']])
            
            # Parse version from description
            version = ""
            version_match = re.search(r"version\s*([0-9a-zA-Z_-]+)", desc, re.IGNORECASE)
            if version_match:
                version = f"Version {version_match.group(1)}"
            elif "new version" in desc_lower:
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

        total_consents_count = Consent.query.count()
        total_sessions_count = Session.query.count()

        # Audio-segmentation ratings need results_json (evaluation / rejection_reasons).
        # Fetch just those rows fully instead of every rating in the DB.
        seg_test_ids = [t.id for t in tests if t.test_type == 'audio-segmentation']
        seg_ratings_by_test = {}
        if seg_test_ids:
            for _r in Rating.query.filter(Rating.test_id.in_(seg_test_ids)).all():
                seg_ratings_by_test.setdefault(_r.test_id, []).append(_r)

        # 3. Audio segmentation: total audio duration per batch + audio hours
        # completed per annotator (durations read from the WAV headers, cached).
        import os as _os
        audio_root = _os.path.join(
            _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
            'audio_segmentation'
        )
        raters_by_id = {r.id: r for r in raters}
        audio_seg_data = []
        for test in tests:
            if test.test_type != 'audio-segmentation':
                continue
            entries = test.json_entry if isinstance(test.json_entry, list) else []
            dur_by_task = {}
            lang_counts = {}
            persona_counts = {}
            for item in entries:
                task_id = str(item.get('id') or '')
                filename = item.get('audio_filename')
                # Track the language / persona of this batch (single-valued per set,
                # but count occurrences and pick the most common to be safe).
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

            # Distinct completed task ids per rater for this test + accept/reject
            # tallies read from each submission's results_json ("evaluation" field).
            done_by_rater = {}
            eval_by_rater = {}   # rater_id -> [accepted, rejected]
            seg_accepted = 0
            seg_rejected = 0
            for r in seg_ratings_by_test.get(test.id, []):
                if not (r.page_no_progress and r.completion_status in ['completed', 'skipped']):
                    continue
                done_by_rater.setdefault(r.rater_id, set()).add(str(r.page_no_progress))
                rj = r.results_json if isinstance(r.results_json, dict) else {}
                ev = str(rj.get('evaluation') or '').strip().lower()
                tally = eval_by_rater.setdefault(r.rater_id, [0, 0])
                if ev == 'accept':
                    seg_accepted += 1
                    tally[0] += 1
                elif ev == 'reject':
                    seg_rejected += 1
                    tally[1] += 1

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
        audio_seg_data.sort(key=lambda x: x['test_id'])

        # 4. Per-task-type overview: for every test type, per-batch progress with
        #    a per-annotator breakdown. Built entirely from tests_data + the
        #    ratings already grouped above, so it never touches the deferred
        #    json_entry column.
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
                    _rj = r.results_json if isinstance(r.results_json, dict) else {}
                    ev = str(_rj.get('evaluation') or '').strip().lower()
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
                'total_consents': total_consents_count,
                'total_sessions': total_sessions_count
            },
            'languages': languages_data,
            'tests': tests_data,
            'raters': raters_data,
            'audio_segmentation': audio_seg_data,
            'audio_seg_artists': _artist_stats_safe(tests, seg_ratings_by_test),
            'task_types': task_types_data
        }
        _dashboard_cache_write(_payload)
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
            
        assigned_tests = Test.query.filter(Test.id.in_(assigned_ids)).all()
        
        # Sort tests in the order they were assigned
        assigned_tests_dict = {t.id: t for t in assigned_tests}
        sorted_tests = [assigned_tests_dict[tid] for tid in assigned_ids if tid in assigned_tests_dict]
        
        languages_list = ["hindi", "bengali", "gujarati", "kannada", "malayalam", "marathi", "odia", "tamil", "telugu", "urdu", "english"]
        
        tasks_data = []
        for test in sorted_tests:
            desc = test.description or "No description"
            lang = ""
            desc_lower = desc.lower()
            for l in languages_list:
                if l in desc_lower:
                    lang = l.capitalize()
                    break
            if not lang:
                if test.json_entry and isinstance(test.json_entry, list) and len(test.json_entry) > 0:
                    first_item = test.json_entry[0]
                    lang = first_item.get('target_language') or first_item.get('language') or first_item.get('metadata', {}).get('language') or ""
                    lang = lang.capitalize() if lang else "Unknown"
                else:
                    lang = "Unknown"
            
            # Progress calculation
            ratings = Rating.query.filter_by(rater_id=rater.id, test_id=test.id).all()
            completed_pages_raw = {rating.page_no_progress for rating in ratings if rating.page_no_progress and rating.completion_status in ['completed', 'skipped']}
            
            all_page_ids = [sample['id'] for sample in test.json_entry] if test.json_entry else []
            completed_count = len([p for p in all_page_ids if str(p) in completed_pages_raw])
            total_count = len(all_page_ids)
            
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


@app.route('/api/admin/rater/<int:rater_id>/assign_tasks', methods=['POST', 'PUT'])
@token_required
def assign_tasks(current_user, rater_id):
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
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
        return jsonify({'message': 'Tasks assigned successfully', 'assigned_tasks': rater.assigned_tasks}), 200
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Error in assign_tasks: {e}")
        return jsonify({'error': 'Failed to assign tasks.'}), 500


# ============================================================================
# Admin -> Annotator messaging, nudges, and reversible account deactivation.
# All additive: messaging never mutates other tables; deactivation only flips a
# flag and stashes/restores assigned_tasks. No Rating (annotation) data is ever
# touched or deleted.
# ============================================================================

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
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
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
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        data = request.get_json() or {}
        body = (data.get('body') or '').strip()
        if not body:
            return jsonify({'message': 'Message body cannot be empty.'}), 400
        if len(body) > 2000:
            body = body[:2000]
        # Broadcast to every real annotator (there is no 'admin' Rater row).
        # Every row of this broadcast shares one broadcast_id so the admin can
        # later view/edit it as a single message rather than N copies.
        broadcast_id = uuid.uuid4().hex
        recipients = Rater.query.all()
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
    """Admin outbox: everything the admin has shared. Individual messages/nudges
    are listed one per row; a broadcast is collapsed into a single entry (grouped
    by broadcast_id) that carries how many recipients have read it. Read-only."""
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater_names = {r.id: r.name for r in Rater.query.all()}
        msgs = Message.query.order_by(Message.created_at.desc()).all()
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
    """Edit the body of an individual message the admin already sent. If the row
    happens to belong to a broadcast, the whole broadcast is updated so every
    recipient stays in sync. Only the body/edited_at change — read state and all
    other tables are left untouched."""
    if current_user != "admin":
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
    """Edit a broadcast (every annotator's copy) in one shot, keyed by the shared
    broadcast_id. Only body/edited_at change."""
    if current_user != "admin":
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
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
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
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
        data = request.get_json() or {}
        confirm = (data.get('confirm') or '').strip()
        # Require the admin to type exactly: delete <name>
        expected = f"delete {rater.name}".strip().lower()
        if confirm.lower() != expected:
            return jsonify({'message': f'Confirmation text did not match. Type "delete {rater.name}" to confirm.'}), 400

        # Reversible: stash the current assignment, then unlock those tasks.
        # Ratings (submitted annotations) are intentionally left untouched.
        if rater.assigned_tasks:
            rater.prev_assigned_tasks = rater.assigned_tasks
        rater.assigned_tasks = ''
        rater.is_active = False
        db.session.commit()
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
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        rater = Rater.query.get_or_404(rater_id)
        rater.is_active = True
        # Restore the previous assignment only if nothing has been assigned since.
        if not rater.assigned_tasks and rater.prev_assigned_tasks:
            rater.assigned_tasks = rater.prev_assigned_tasks
        rater.prev_assigned_tasks = ''
        db.session.commit()
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
    if current_user == "admin":
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
    if current_user == "admin":
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