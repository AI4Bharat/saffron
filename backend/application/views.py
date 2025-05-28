from flask import jsonify, request
from werkzeug.security import generate_password_hash
from flask import current_app as app
from application.models import db, Rater, Test, Rating, Study, Session, Consent
from datetime import datetime, timedelta
import jwt
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

# Set up logging
if not app.debug:
    handler = RotatingFileHandler('error.log', maxBytes=10000, backupCount=1)
    handler.setLevel(logging.ERROR)
    app.logger.addHandler(handler)


@app.errorhandler(Exception)
def unhandled_exception(e):
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
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    user = Rater.query.filter_by(name=username).first()
    if user and user.password == password:
        auth_token = generate_token(username)
        return jsonify({'token': auth_token}), 200
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
    rater_id = Rater.query.filter_by(name=required["username"]).first_or_404().id
    test = Test.query.filter_by(id=test_id).first_or_404()

    # Get the page numbers that the rater has already done and shuffle the remaining samples
    page_nos_done = Rating.query.filter_by(rater_id=rater_id, test_id=test_id).with_entities(Rating.page_no_progress).all()
    page_nos_done = [page_no[0] for page_no in page_nos_done]
    page_nos_done = list(map(int, page_nos_done))
    samples = [sample for sample in test.json_entry if sample['id'] not in page_nos_done]
    random.shuffle(samples)
    samples_done = [sample for sample in test.json_entry if sample['id'] in page_nos_done]
    samples_done.extend(samples)
    required = samples_done

    try:
        page_no = len(page_nos_done)
    except:
        page_no = 0

    return jsonify({
        'test_id': test.id,
        'test_type': test.test_type,
        'description': test.description,
        'json_entry': required,
        'page_no': page_no
    })


@app.route('/api/ratings', methods=['POST'])
@token_required
def create_rating(current_user):
    try:
        token = request.headers.get('Authorization').split()[1]
        required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
        rater = Rater.query.filter_by(name=required["username"]).first_or_404()
        data = request.get_json()

        if 'results_json' not in data or not isinstance(data['results_json'], dict):
            return jsonify({'message': 'Invalid results_json format'}), 400

        data['results_json']['test_id'] = data['test_id']
        data['results_json']['rater_email'] = rater.email
        data['results_json']['time'] = datetime.now().isoformat()
        data['results_json']['time_taken'] = data['time_taken_to_submit'] / 1000
        data['results_json']['data_id'] = data.get('pageNo_progress')

        rating = Rating(
            id=db.session.query(db.func.max(Rating.id)).scalar() + 1 if db.session.query(db.func.max(Rating.id)).scalar() is not None else 1,
            rater_id=rater.id,
            test_id=data['test_id'],
            results_json=data['results_json'],
            time_taken_to_submit=data['time_taken_to_submit'],
            page_no_progress=data.get('pageNo_progress')
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
    ).with_entities(Rating.page_no_progress).all()
    completed_pages = {int(rating.page_no_progress)
                       for rating in ratings if rating.page_no_progress}

    # Get all pages in the test
    all_pages = [entry['id'] for entry in test.json_entry]

    # Filter out completed pages and shuffle the remaining ones
    remaining_pages = [page for page in all_pages if page not in completed_pages]
    random.shuffle(remaining_pages)

    # Create a dictionary for quick lookup of entries by ID
    entry_dict = {entry['id']: entry for entry in test.json_entry}

    # Combine completed pages (preserving their order) with shuffled remaining pages
    full_test_sequence = [entry_dict[page_id] for page_id in completed_pages] + \
                         [entry_dict[page_id] for page_id in remaining_pages]

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
        "time_taken_to_submit": 300
    }
    """
    data = request.get_json()
    session_id = data.get('session_id')
    test_id = data.get('test_id')
    results_json = data.get('results_json')
    time_taken_to_submit = data.get('time_taken_to_submit')

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
        page_no_progress=data.get('pageNo_progress')
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
            'page_no_progress': rating.page_no_progress
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
            'page_no_progress': rate.page_no_progress
        })
    return jsonify(results)


@app.route('/api/verify_test/<int:test_id>', methods=['GET'])
def verify_test(test_id):
    token = request.headers.get('Authorization').split()[1]
    required = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
    
    rater = Rater.query.filter_by(name=required["username"]).first_or_404()
    if not rater:
        return jsonify({'message': 'Rater not found'}), 404
    
    test = Test.query.filter_by(id=test_id).first_or_404()
    if not test:
        return jsonify({'message': 'Test not found'}), 404

    ratings = Rating.query.filter_by(
                rater_id=rater.id, test_id=test.id
            ).with_entities(Rating.page_no_progress).all()
    completed_pages = {int(rating.page_no_progress)
                       for rating in ratings if rating.page_no_progress}

    # Get all pages in the test
    all_pages = [entry['id'] for entry in test.json_entry]

    # Filter out completed pages and shuffle the remaining ones
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
                test_groups.setdefault(test_id, 0)
                test_groups[test_id] += 1

            for test_id, completed in test_groups.items():
                test = Test.query.get(test_id)
                total = len(test.json_entry) if test and test.json_entry else 0
                tracking_data.append({
                    'email': rater.email,
                    'test_id': test.id,
                    'test_type': test.test_type,
                    'test_desc': test.description,
                    'completed_pages': completed,
                    'total_pages': total
                })

        tracking_data.sort(key=lambda x: x['test_id'], reverse=True)
        return jsonify(tracking_data)
    except Exception as e:
        app.logger.error(f"Error in tracking endpoint: {e}")
        return jsonify({'error': 'Failed to fetch tracking data.'}), 500