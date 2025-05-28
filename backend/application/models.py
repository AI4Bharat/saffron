from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from application.database import db


class Rater(db.Model):
    __tablename__ = 'rater'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # Ensure you hash passwords

    ratings = db.relationship('Rating', backref='rater', lazy=True)

    def __repr__(self):
        return f"<Rater {self.name}>"


class Test(db.Model):
    __tablename__ = 'test'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    test_type = db.Column(db.String(512), nullable=False)  # Increased length for PostgreSQL
    description = db.Column(db.Text, nullable=True)
    json_entry = db.Column(db.JSON, nullable=False)  # JSON column for PostgreSQL

    ratings = db.relationship('Rating', backref='test', lazy=True)

    def __repr__(self):
        return f"<Test {self.test_type}>"


class Study(db.Model):
    __tablename__ = 'study'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    study_id = db.Column(db.String(100), nullable=False, unique=True)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    completion_url = db.Column(db.String(512), nullable=False)

    test = db.relationship('Test', backref='studies', lazy=True)

    def __repr__(self):
        return f"<Study Study ID={self.study_id}, Test ID={self.test_id}>"


class Session(db.Model):
    __tablename__ = 'session'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.String(100), nullable=False, unique=True)
    study_id = db.Column(db.Integer, db.ForeignKey('study.id'), nullable=False)
    prolific_pid = db.Column(db.String(100), nullable=False)

    study = db.relationship('Study', backref='sessions', lazy=True)

    def __repr__(self):
        return f"<Session Session ID={self.session_id}, Study ID={self.study_id}>"


class Rating(db.Model):
    __tablename__ = 'rating'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    results_json = db.Column(db.JSON, nullable=False)  # JSON column for PostgreSQL
    time_of_submission = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    time_taken_to_submit = db.Column(db.Float, nullable=False)  # Assuming seconds
    page_no_progress = db.Column(db.String(50), nullable=True)  # Page or progress

    def __repr__(self):
        return f"<Rating Rater ID={self.rater_id}, Test ID={self.test_id}>"

class Consent(db.Model):
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    rater_id = db.Column(db.Integer, db.ForeignKey('rater.id'), nullable=False)
    test_id = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    time_of_submission = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Consent Rater ID={self.rater_id}>, Test ID={self.test_id}>"