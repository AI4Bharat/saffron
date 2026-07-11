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
        return e
    app.logger.error('Unhandled Exception: %s', (e))
    return jsonify({'message': 'Internal Server Error'}), 500


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


@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()

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
        id=db.session.query(db.func.max(Rater.id)).scalar() + 1 if db.session.query(db.func.max(Rater.id)).scalar() is not None else 1,
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
    token = request.headers.get('Authorization').split()[1]
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
    
    completed_pages_raw = {pid for pid, val in latest_status.items() if val['status'] in ['completed', 'skipped']}
    
    # Safely match original IDs with the string IDs from rating
    all_page_ids = [sample['id'] for sample in test.json_entry]
    page_nos_done = [pid for pid in all_page_ids if str(pid) in completed_pages_raw]
    
    samples = [sample for sample in test.json_entry if sample['id'] not in page_nos_done]
    # Keep tasks in the original order instead of shuffling
    # random.shuffle(samples)
    samples_done = [sample for sample in test.json_entry if sample['id'] in page_nos_done]
    samples_done.extend(samples)
    
    # Map latest ratings by task ID to merge corrections
    latest_ratings = {}
    for r in ratings:
        if r.page_no_progress:
            pid = str(r.page_no_progress)
            if pid not in latest_ratings or r.time_of_submission > latest_ratings[pid].time_of_submission:
                latest_ratings[pid] = r

    # Inject completion_status and merge corrected translations into each entry
    required_response = []
    for sample in samples_done:
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

    try:
        page_no = len(page_nos_done)
    except:
        page_no = 0

    return jsonify({
        'test_id': test.id,
        'test_type': test.test_type,
        'description': test.description,
        'json_entry': required_response,
        'page_no': page_no
    })


@app.route('/api/ratings', methods=['POST'])
@token_required
def create_rating(current_user):
    try:
        token = request.headers.get('Authorization').split()[1]
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
                id=db.session.query(db.func.max(Rating.id)).scalar() + 1 if db.session.query(db.func.max(Rating.id)).scalar() is not None else 1,
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
        id = db.session.query(db.func.max(Study.id)).scalar() + 1 if db.session.query(db.func.max(Study.id)).scalar() is not None else 1,
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
            id=db.session.query(db.func.max(Rater.id)).scalar() + 1 if db.session.query(db.func.max(Rater.id)).scalar() is not None else 1,
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
    token = request.headers.get('Authorization').split()[1]
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
        id = db.session.query(db.func.max(Rating.id)).scalar() + 1 if db.session.query(db.func.max(Rating.id)).scalar() is not None else 1,
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
            id=db.session.query(db.func.max(Test.id)).scalar() + 1 if db.session.query(db.func.max(Test.id)).scalar() is not None else 1,
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
    token = request.headers.get('Authorization').split()[1]
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
    token = request.headers.get('Authorization').split()[1]
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
    token = request.headers.get('Authorization').split()[1]
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
    token = request.headers.get('Authorization').split()[1]
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
                total = len(test.json_entry) if test and test.json_entry else 0
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


@app.route('/api/admin/dashboard', methods=['GET'])
@token_required
def get_admin_dashboard(current_user):
    if current_user != "admin":
        return jsonify({'message': 'Unauthorized'}), 401
    try:
        from sqlalchemy.orm import defer
        import re

        # 1. Fetch all raters and all ratings once to avoid N+1 queries
        raters = Rater.query.all()
        total_registered_users = len(raters)
        
        all_ratings = Rating.query.all()
        
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
            for r in ratings_by_test.get(test.id, []):
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

        return jsonify({
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
            'audio_segmentation': audio_seg_data
        })
        
    except Exception as e:
        app.logger.error(f"Error in admin dashboard endpoint: {e}")
        return jsonify({'error': 'Failed to load admin dashboard statistics.'}), 500


@app.route('/api/rater/tasks', methods=['GET'])
@token_required
def get_assigned_tasks(current_user):
    try:
        token = request.headers.get('Authorization').split()[1]
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