from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    balance = db.Column(db.Float, default=500.0)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    bets = db.relationship('Bet', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def total_wagered(self):
        return sum(b.amount for b in self.bets if b.status != 'cancelled')

    @property
    def total_won(self):
        return sum(b.potential_win for b in self.bets if b.status == 'won')


class Event(db.Model):
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(200))
    race_date = db.Column(db.DateTime, nullable=False)
    image_url = db.Column(db.String(500))
    status = db.Column(db.String(20), default='upcoming')  # upcoming, live, finished, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    markets = db.relationship('Market', backref='event', lazy=True, cascade='all, delete-orphan')

    @property
    def open_markets_count(self):
        return sum(1 for m in self.markets if m.status == 'open')


class Market(db.Model):
    __tablename__ = 'markets'
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    market_type = db.Column(db.String(50))
    status = db.Column(db.String(20), default='open')  # open, suspended, closed, resolved
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    selections = db.relationship('Selection', backref='market', lazy=True, cascade='all, delete-orphan')

    @property
    def total_bets_amount(self):
        total = 0
        for s in self.selections:
            total += sum(b.amount for b in s.bets if b.status != 'cancelled')
        return total


class Selection(db.Model):
    __tablename__ = 'selections'
    id = db.Column(db.Integer, primary_key=True)
    market_id = db.Column(db.Integer, db.ForeignKey('markets.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.String(500))
    flag = db.Column(db.String(10))
    odds = db.Column(db.Float, nullable=False)
    base_odds = db.Column(db.Float, nullable=False)  # Cote initiale, jamais modifiée
    is_winner = db.Column(db.Boolean, default=False)
    bets = db.relationship('Bet', backref='selection', lazy=True)

    @property
    def total_bets(self):
        return len([b for b in self.bets if b.status != 'cancelled'])

    @property
    def total_staked(self):
        return sum(b.amount for b in self.bets if b.status != 'cancelled')


class Bet(db.Model):
    __tablename__ = 'bets'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    selection_id = db.Column(db.Integer, db.ForeignKey('selections.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    potential_win = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, won, lost, cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved_at = db.Column(db.DateTime)
