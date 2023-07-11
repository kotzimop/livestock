# app/admin/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, SubmitField, IntegerField, DateField, SelectField
from wtforms.validators import DataRequired, Optional
from wtforms_sqlalchemy.fields import QuerySelectField
from ..models import Alert, ExpenseCategory, IncomeCategory



class MilkingForm(FlaskForm):
    """
    Form for admin to add or edit a milking record
    """
    ear_tag = IntegerField('Ear Tag')
    amount = FloatField('Amount')
    box = SelectField('Box',choices=[(0, 'Επιλογή Box'),('1',1),('2',2),('3',3),('4',4),('5',5),('6',6),('7',7),('8',8),('9',9),('10',10)], default=0)
    submit = SubmitField('Submit')

class StopMilkingForm(FlaskForm):
    """
    Form for admin to stop milking periods
    """
    ear_tag = IntegerField('Ear Tag')
    submit = SubmitField('Submit')




class SingleMilkingForm(FlaskForm):
    """
    Form for admin to add a single milking record
    """
    ear_tag = IntegerField('Ενώτιο')
    amount = FloatField('Ποσότητα')
    date_field = SelectField("Project Model",
                             choices=['MORNING', 'MIDDAY', 'EVENING'])
    submit = SubmitField('Submit')


class AnimalForm(FlaskForm):
    """
    Form for admin to add or edit an animal record
    """
    ear_tag = IntegerField('Ενώτιο', validators=[DataRequired()])
    date_of_birth = DateField('Ημερομηνία Γέννησης',
                              validators=[DataRequired()])
    parent_ear_tag = IntegerField("Ενώτιο Γονέα", validators=[Optional()])
    submit = SubmitField('Υποβολή')


class AlertForm(FlaskForm):
    """
    Form for admin to add or edit an alert record
    """
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Submit')


class AnimalAlertForm(FlaskForm):
    """
    Form for admin to link or edit a relationship between sheep and alerts
    """
    animal = IntegerField('Animal', validators=[DataRequired()])
    alert = QuerySelectField(query_factory=lambda: Alert.query.all(),
                             get_label="name")
    date_recorded = DateField(
        'Date of Birth', format='%Y-%m-%d', validators=[Optional()])
    submit = SubmitField('Submit')


class ParentForm(FlaskForm):
    """
    Form for admin to add births to animals
    """
    child = IntegerField('Child')
    date_of_birth = DateField('Date of Birth')
    submit = SubmitField('Submit')


class ShipmentForm(FlaskForm):
    """
    Form for admin to add shipment data to database
    """
    amount = FloatField('Amount', validators=[DataRequired()])
    date_recorded = DateField('Date of Birth', validators=[DataRequired()])
    submit = SubmitField('Submit')


class IncomeForm(FlaskForm):
    """
    Form for admin to add income data to database
    """
    amount = FloatField('Amount', validators=[DataRequired()])
    category = QuerySelectField('Category', query_factory=lambda: IncomeCategory.query.all(),
                                get_label="name")
    date_recorded = DateField('Date Recorded', validators=[DataRequired()])
    submit = SubmitField('Submit')


class IncomeCategoryForm(FlaskForm):
    """
    Form for admin to add income category data to database
    """
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Submit')


class ExpenseForm(FlaskForm):
    """
    Form for admin to add expense data to database
    """
    amount = FloatField('Amount', validators=[DataRequired()])
    category = QuerySelectField('Category', query_factory=lambda: ExpenseCategory.query.all(),
                                get_label="name")
    date_recorded = DateField('Date Recorded', validators=[DataRequired()])
    submit = SubmitField('Submit')


class ExpenseCategoryForm(FlaskForm):
    """
    Form for admin to add expense category data to database
    """
    name = StringField('Name', validators=[DataRequired()])
    submit = SubmitField('Submit')
