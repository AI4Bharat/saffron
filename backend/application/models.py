from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from application.database import db




class Team(db.Model):
    """One workspace inside the organisation (e.g. 'tts', 'asr')."""
    __tablename__ = 'team'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(32), unique=True, nullable=False)      # url/token-safe: 'tts'
    name = db.Column(db.String(120), nullable=False)                 # 'TTS Team'
    description = db.Column(db.Text, nullable=True)
    # 'classic' -> batch/assignment workflow (Test + Rating), the original TTS flow 'pool' -> single pool of items annotators pull from (the ASR flow)
    workflow = db.Column(db.String(32), nullable=False, default='classic')
    accent = db.Column(db.String(16), nullable=True, default='#4f46e5')  # UI accent colour
    # Team-level behaviour switches the admin flips from the dashboard (e.g. 'difficulty_annotation': false hides the difficulty step for annotators). A JSON bag so a new switch needs no schema change.
    settings = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Team {self.key}>"


class TeamMember(db.Model):
    """An annotator's membership of a team. One row per (team, rater)."""
    __tablename__ = 'team_member'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False)
    role = db.Column(db.String(32), nullable=False, default='annotator')
    # Pool teams only: the languages this annotator may be handed work in (comma separated; empty = every language the pool has).
    languages = db.Column(db.String(512), nullable=True, default='')
    # Pool teams only: how many items one "Get work" press hands out, and the ceiling on how many claimed-but-unfinished items they may hold.
    pull_size = db.Column(db.Integer, nullable=False, default=50)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint('team_id', 'rater_id', name='uq_team_member'),)

    team = db.relationship('Team', backref='members', lazy=True)
    rater = db.relationship('Rater', backref='team_links', lazy=True)

    def __repr__(self):
        return f"<TeamMember team={self.team_id} rater={self.rater_id}>"


class AdminUser(db.Model):
    """A dashboard login."""
    __tablename__ = 'admin_user'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(120), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    team = db.relationship('Team', backref='admins', lazy=True)

    @property
    def scope(self):
        return 'org' if self.team_id is None else 'team'

    def __repr__(self):
        return f"<AdminUser {self.username} scope={self.scope}>"


class PoolUpload(db.Model):
    """One bulk upload of pool items -- the whole ASR sheet arrives as a single upload, and every item points back at it."""
    __tablename__ = 'pool_upload'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    source = db.Column(db.Text, nullable=True)          # sheet URL / file path
    item_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    team = db.relationship('Team', backref='uploads', lazy=True)

    def __repr__(self):
        return f"<PoolUpload {self.name} n={self.item_count}>"


class PoolTask(db.Model):
    """One pool TASK: every item of a single (language, class, kind of work) in a team's pool."""
    __tablename__ = 'pool_task'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False, index=True)
    language = db.Column(db.String(64), nullable=False)
    class_label = db.Column(db.String(32), nullable=True)
    # The kind of work this task's items are (mirrors PoolItem.task_type), so a future task type forms its own tasks instead of merging into existing ones.
    task_type = db.Column(db.String(64), nullable=False, default='text-review')
    item_count = db.Column(db.Integer, nullable=False, default=0)
    # Per-task behaviour overrides (JSON bag). Known keys: 'difficulty_annotation' (bool, overrides the team default for this language+class) and 'difficulty_annotation_by_category' ({category: bool}, overrides both for one category).
    settings = db.Column(db.JSON, nullable=True)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (db.UniqueConstraint('team_id', 'language', 'class_label', 'task_type',
                                          name='uq_pool_task'),)

    @property
    def label(self):
        base = (f"{self.language} · Class {self.class_label}"
                if self.class_label else self.language)
        if self.task_type and self.task_type != 'text-review':
            base += f" · {self.task_type.replace('-', ' ').replace('_', ' ')}"
        return base

    def __repr__(self):
        return f"<PoolTask {self.id} {self.language}/{self.class_label}>"


class PoolAnnotation(db.Model):
    """One annotator's answer to one prompt, covering both the claim and the submission.

    A prompt may be answered by several annotators (the project's max_annotators is
    the target). Keeping answers here rather than on PoolItem is what makes that
    possible: the item can only hold one, so a second submission would overwrite
    the first. The row is created when the prompt is pulled and completed when it
    is submitted, so a claim in flight is visible without a second table.
    """
    __tablename__ = 'pool_annotation'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    item_id = db.Column(db.Integer, db.ForeignKey('pool_item.id'), nullable=False, index=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False, index=True)
    team_id = db.Column(db.Integer, nullable=True)
    task_id = db.Column(db.Integer, nullable=True)
    pull_id = db.Column(db.String(64), nullable=True, index=True)
    # 'claimed' -> in someone's hands; 'completed' / 'flagged' -> answered.
    status = db.Column(db.String(16), nullable=False, default='claimed')
    final_text = db.Column(db.Text, nullable=True)
    final_difficulty = db.Column(db.String(32), nullable=True)
    is_edited = db.Column(db.Boolean, nullable=False, default=False)
    is_flagged = db.Column(db.Boolean, nullable=False, default=False)
    flag_reason = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    # Score-based work (MDFS and friends) submits a dict instead of edited text.
    results_json = db.Column(db.JSON, nullable=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    time_taken_ms = db.Column(db.Integer, nullable=True)
    revision = db.Column(db.Integer, nullable=False, default=0)

    # One answer per person per prompt; an edit updates the row they already have.
    __table_args__ = (db.UniqueConstraint('item_id', 'rater_id',
                                          name='uq_pool_annotation_item_rater'),)

    def __repr__(self):
        return f"<PoolAnnotation item={self.item_id} rater={self.rater_id} {self.status}>"


class PoolTaskAssignment(db.Model):
    """The admin hands one task -- or one CATEGORY inside a task -- to an annotator. category NULL means the whole task. Several annotators may hold the same task (or the same category) at once and share its pool of prompts; each PROMPT still goes to exactly one annotator, because a pull claims rows atomically (see pool_pull)."""
    __tablename__ = 'pool_task_assignment'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task_id = db.Column(db.Integer, db.ForeignKey('pool_task.id'), nullable=False, index=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False, index=True)
    # NULL = the whole task; otherwise one category (word/sentence/...) inside it.
    category = db.Column(db.String(64), nullable=True)
    assigned_by = db.Column(db.String(80), nullable=True)     # admin username
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    revoked_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (db.UniqueConstraint('task_id', 'rater_id', 'category',
                                          name='uq_pool_task_assignment'),)

    task = db.relationship('PoolTask', backref='assignments', lazy=True)
    rater = db.relationship('Rater', backref='pool_task_assignments', lazy=True)

    def __repr__(self):
        return f"<PoolTaskAssignment task={self.task_id} rater={self.rater_id}>"


class PoolPull(db.Model):
    """One "get prompts" press: the smaller bucket an annotator carved out of a task they were assigned."""
    __tablename__ = 'pool_pull'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pull_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey('pool_task.id'), nullable=True, index=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False, index=True)
    # The granularity the annotator chose inside the task ('' = the whole task).
    category = db.Column(db.String(64), nullable=True)
    source_difficulty = db.Column(db.String(32), nullable=True)
    requested = db.Column(db.Integer, nullable=False, default=0)
    item_count = db.Column(db.Integer, nullable=False, default=0)
    # 'open' -> still being worked | 'released' -> handed back by the annotator or an admin.
    status = db.Column(db.String(16), nullable=False, default='open')
    # 'self' when the annotator pulled it, 'admin' when an admin pushed it.
    origin = db.Column(db.String(16), nullable=False, default='self')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    released_at = db.Column(db.DateTime, nullable=True)

    task = db.relationship('PoolTask', backref='pulls', lazy=True)

    def __repr__(self):
        return f"<PoolPull {self.pull_id} task={self.task_id} rater={self.rater_id}>"


class PoolItem(db.Model):
    """A single annotatable item in a team's pool."""
    __tablename__ = 'pool_item'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=False)
    upload_id = db.Column(db.Integer, db.ForeignKey('pool_upload.id'), nullable=True)
    item_key = db.Column(db.String(64), nullable=True)      # stable external id
    # What kind of work this item is.
    task_type = db.Column(db.String(64), nullable=False, default='text-review')

    # The task this item belongs to -- always the PoolTask for its own (language, class).
    task_id = db.Column(db.Integer, db.ForeignKey('pool_task.id'), nullable=True, index=True)

    # --- metadata carried straight from the source sheet ---
    language = db.Column(db.String(64), nullable=False, index=True)
    class_label = db.Column(db.String(32), nullable=True)   # school class 1..5
    category = db.Column(db.String(64), nullable=True)      # word/sentence/paragraph/poem
    source_difficulty = db.Column(db.String(32), nullable=True)   # as generated
    source = db.Column(db.String(64), nullable=True)        # gemini/textbook
    n_words = db.Column(db.Integer, nullable=True)
    text = db.Column(db.Text, nullable=False)               # ORIGINAL text, never overwritten
    extra_json = db.Column(db.JSON, nullable=True)          # any further sheet columns

    # 'available' -> nobody holds it | 'claimed' -> locked to claimed_by 'completed' -> annotated | 'flagged' -> annotated as unusable
    status = db.Column(db.String(16), nullable=False, default='available', index=True)
    claimed_by = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=True, index=True)
    claimed_at = db.Column(db.DateTime, nullable=True)
    pull_id = db.Column(db.String(40), nullable=True, index=True)   # groups one "Get work" press

    # --- annotation result ---
    final_text = db.Column(db.Text, nullable=True)          # annotator's corrected text
    final_difficulty = db.Column(db.String(32), nullable=True)
    is_edited = db.Column(db.Boolean, nullable=False, default=False)
    is_flagged = db.Column(db.Boolean, nullable=False, default=False)
    flag_reason = db.Column(db.String(255), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    completed_by = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=True, index=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    time_taken_ms = db.Column(db.Integer, nullable=True)
    revision = db.Column(db.Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<PoolItem {self.id} {self.language}/{self.class_label} {self.status}>"


class Rater(db.Model):
    __tablename__ = 'rater'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Ensure you hash passwords
    assigned_tasks = db.Column(db.String(1024), nullable=True, default='')
    # Account state for admin deactivation.
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    prev_assigned_tasks = db.Column(db.String(1024), nullable=True, default='')

    ratings = db.relationship('Rating', backref='rater', lazy=True)

    def __repr__(self):
        return f"<Rater {self.name}>"


class Test(db.Model):
    __tablename__ = 'test'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_type = db.Column(db.String(512), nullable=False)  # Increased length for PostgreSQL
    description = db.Column(db.Text, nullable=True)
    json_entry = db.Column(db.JSON, nullable=False)  # JSON column for PostgreSQL
    # Admin-controlled.
    handoff_mode = db.Column(db.Boolean, nullable=False, default=False)
    # Which team owns this batch.
    team_id = db.Column(db.Integer, db.ForeignKey('team.id'), nullable=True, index=True)
    # Denormalised facts about json_entry, filled once when the batch is loaded.
    item_count = db.Column(db.Integer, nullable=True)
    language_hint = db.Column(db.String(64), nullable=True)

    ratings = db.relationship('Rating', backref='test', lazy=True)

    def __repr__(self):
        return f"<Test {self.test_type}>"


# NOTE: the Study / Session / Consent models were removed on 2026-08-06 together with the retired Prolific recruitment flow.


class Rating(db.Model):
    __tablename__ = 'rating'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    results_json = db.Column(db.JSON, nullable=False)  # JSON column for PostgreSQL
    time_of_submission = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    time_taken_to_submit = db.Column(db.Float, nullable=False)  # Assuming seconds
    page_no_progress = db.Column(db.String(128), nullable=True)  # Page or progress (real data has exceeded 50 chars; PostgreSQL enforces the declared size)
    completion_status = db.Column(db.String(50), nullable=True, default='completed')
    # The accept/reject verdict lifted out of results_json when the row is written.
    verdict = db.Column(db.String(16), nullable=True)

    def __repr__(self):
        return f"<Rating Rater ID={self.rater_id}, Test ID={self.test_id}>"

class Message(db.Model):
    """Admin -> annotator messages."""
    __tablename__ = 'message'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False)  # recipient
    body = db.Column(db.Text, nullable=False)
    sender = db.Column(db.String(100), nullable=False, default='admin')
    category = db.Column(db.String(50), nullable=True, default='message')  # 'message' | 'nudge' | 'broadcast'
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    # A single "broadcast" fans out to one Message row per annotator; they all share this id so the admin can view/edit the broadcast as one thing.
    broadcast_id = db.Column(db.String(64), nullable=True, index=True)
    # Set when an admin edits the body after sending; NULL if never edited.
    edited_at = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f"<Message to Rater ID={self.rater_id}, read={self.is_read}>"