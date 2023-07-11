# app/models.py

from flask_login import UserMixin
from sqlalchemy import BigInteger, UniqueConstraint, Date, cast
from sqlalchemy.orm import column_property
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import date, datetime, timedelta

from app import db, login_manager


class User(UserMixin, db.Model):
    """
    Create a User table
    """

    # Ensures table will be named in plural and not in singular
    # as is the name of the model
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(60), index=True, unique=True)
    username = db.Column(db.String(60), index=True, unique=True)
    first_name = db.Column(db.String(60), index=True)
    last_name = db.Column(db.String(60), index=True)
    password_hash = db.Column(db.String(128))
    is_admin = db.Column(db.Boolean, default=False)

    @property
    def password(self):
        """
        Prevent password from being accessed
        """
        raise AttributeError('password is not a readable attribute.')

    @password.setter
    def password(self, password):
        """
        Set password to a hashed password
        """
        self.password_hash = generate_password_hash(password)

    def verify_password(self, password):
        """
        Check if hashed password matches actual password
        """
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User: {}>'.format(self.username)

    def to_dict(self):
        return {
            'username': self.username,
            'email': self.email
        }

# Set up user_loader


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class Animal(db.Model):
    """
    Create an Animal table
    """

    __tablename__ = 'animals'

    id = db.Column(db.Integer, primary_key=True)
    ear_tag = db.Column(db.BigInteger(), unique=True)
    date_of_birth = db.Column(db.Date())
    status = db.Column(db.Boolean, default=True)
    animal_box = db.Column(db.Integer, nullable=True)
    milkigs = db.relationship('Milking', backref='animal',
                              lazy='dynamic')
    alerts = db.relationship(
        'AnimalAlert', backref='animal_id_alert', lazy='dynamic')
    set_milking_period = db.relationship(
        "AnimalMilkingPeriods", backref="set_milking_period", lazy='dynamic')

    def __repr__(self):
        return '<Animal: {}>'.format(self.ear_tag)

    def to_dict(self):
        return {
            'id': self.id,
            'ear_tag': self.ear_tag,
            'date_of_birth': self.date_of_birth.strftime(
                "%Y-%m-%d"),
            'status': self.status
        }


class Milking(db.Model):
    """
    Create a Milking table
    """

    __tablename__ = 'milkings'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float(), nullable=False)
    date_recorded = db.Column(db.DateTime(), nullable=False)
    ear_tag = db.Column(db.BigInteger(), nullable=False)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    days_from_last_birth = db.Column(db.Integer)
    milking_time = db.Column(db.String(60), index=True, unique=False)
    milking_period = db.Column(db.Integer, index=True, unique=False)
    change_from_last_milking = db.Column(db.Float(), nullable=True)
    total_milk_up_to_today = db.Column(db.Integer(), nullable=True)
    __table_args__ = (UniqueConstraint('animal_id', 'days_from_last_birth', 'milking_time', name='uniqueDateTimeMilking'),
                      )

    def __repr__(self):
        return '<Milking: {}>'.format(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'date_recorded': self.date_recorded.strftime(
                "%Y-%m-%d"),
            'ear_tag': self.ear_tag,
            'animal_id': self.animal_id,
            'days_from_last_birth': self.days_from_last_birth,
            'milking_time': self.milking_time,
            'milking_period': self.milking_period,
            'change_from_last_milking': self.change_from_last_milking,
            'total_milk_up_to_today': self.total_milk_up_to_today
        }


class MilkingPerDay(db.Model):
    """
    Create a Milking table
    """

    __tablename__ = 'milkings_per_day'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float(), nullable=False)
    date_recorded = db.Column(db.Date(), unique=True, nullable=False)
    num_of_animals_milked = db.Column(db.Integer)

    def __repr__(self):
        return '<Milking Per Day: {}>'.format(self.id)


class Alert(db.Model):
    """
    Create an Alert table
    """

    __tablename__ = 'alerts'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True, nullable=False)
    alerts = db.relationship(
        'AnimalAlert', backref='alert_id_alert', cascade="all, delete-orphan", lazy='dynamic')

    def __repr__(self):
        return '<Alert: {}>'.format(self.id)


class AnimalAlert(db.Model):
    """
    Create a table many-to-many that links animal with alerts
    """

    __tablename__ = 'animal_alerts'
    id = db.Column(db.Integer, primary_key=True)
    date_recorded = db.Column(db.Date(), nullable=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    alert_id = db.Column(db.Integer, db.ForeignKey('alerts.id'))

    def to_dict(self):
        return {
            'id': self.id,
            'date_recorded': self.date_recorded,
            'animal_id': self.animal_id,
            'alert_id': self.alert_id
        }


class AnimalBirth(db.Model):
    """
    Create a table one-to-many that links parent with children
    """

    __tablename__ = 'animal_births'
    id = db.Column(db.Integer, primary_key=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    child_id = db.Column(db.Integer, db.ForeignKey('animals.id'), unique=True)

    parent = db.relationship("Animal", backref="parent",
                             uselist=False, foreign_keys=[parent_id])
    child = db.relationship("Animal", backref="child",
                            uselist=False, foreign_keys=[child_id])


class AnimalMilkingPeriods(db.Model):
    """
    Create a table one-to-many that links parent with milking periods
    """

    __tablename__ = 'animal_milking_periods'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'))
    milking_period = db.Column(db.Integer)
    start_of_milking_period = db.Column(db.Date(), nullable=False)
    end_of_milking_period = db.Column(db.Date(), nullable=True)
    

    length_of_milking_period = column_property(
        date.today() - start_of_milking_period
    )
    has_child = db.Column(db.Boolean, default=True)

    # Add method in order from animals table to retrieve milking periods


class Shipment(db.Model):
    """
    Create a Shipment table
    """

    __tablename__ = 'shipments'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float(), nullable=False)
    date_recorded = db.Column(db.DateTime(), nullable=False, unique=True)

    def __repr__(self):
        return '<Shipment: {}>'.format(self.id)


class Income(db.Model):
    """
    Create an Income table
    """

    __tablename__ = 'incomes'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float(), nullable=False)
    date_recorded = db.Column(db.DateTime(), nullable=False, unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('income_categories.id'))

    def __repr__(self):
        return '<Income: {}>'.format(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'date_recorded': self.date_recorded.strftime(
                "%Y-%m-%d"),
            'category_id': self.category_id
        }


class IncomeCategory(db.Model):
    """
    Create a Category of Income table
    """

    __tablename__ = 'income_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True, nullable=False)
    income = db.relationship(
        'Income', backref='income_id', lazy='dynamic')

    def __repr__(self):
        return '<Income: {}>'.format(self.id)


class Expense(db.Model):
    """
    Create an Expense table
    """

    __tablename__ = 'expenses'

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float(), nullable=False)
    date_recorded = db.Column(db.DateTime(), nullable=False, unique=True)
    category_id = db.Column(db.Integer, db.ForeignKey('expense_categories.id'))

    def __repr__(self):
        return '<Expense: {}>'.format(self.id)


class ExpenseCategory(db.Model):
    """
    Create a Category of Expense table
    """

    __tablename__ = 'expense_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(), unique=True, nullable=False)
    expense = db.relationship(
        'Expense', backref='expense_id', lazy='dynamic')

    def __repr__(self):
        return '<Expense: {}>'.format(self.id)
