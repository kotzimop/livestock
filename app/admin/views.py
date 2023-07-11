# app/admin/views.py

from .custom_query import expense_per_month, get_statistics_query, getMilkingData, conn, income_per_month, income_vs_expense
from flask import Blueprint, abort, flash, request, redirect, render_template, url_for, jsonify, json, send_file
from flask_login import current_user, login_required
from datetime import date, datetime, timedelta
from sqlalchemy import func, extract, cast, and_,String, asc, Date
from .forms import AlertForm, AnimalAlertForm, ExpenseCategoryForm, ExpenseForm, IncomeCategoryForm, IncomeForm, MilkingForm, AnimalForm, ParentForm, ShipmentForm, StopMilkingForm
from .. import db
from ..models import Income, IncomeCategory, Milking, Animal, MilkingPerDay, Alert, AnimalAlert, AnimalBirth, Shipment, Expense, ExpenseCategory, AnimalMilkingPeriods
import psycopg2.extras
import math


admin = Blueprint('admin', __name__)


def check_admin():
    """
    Prevent non-admins from accessing the page
    """
    if not current_user.is_admin:
        abort(403)

##############################################################
##############################################################
################### Dashboard Views ##########################
##############################################################
##############################################################


@admin.route('/api/new_admin_v2', methods=['GET', 'POST'])
def api_new_admin_v2():
    if request.method == 'POST':
        selected_year = request.form.get('year')
        selected_period_for_analytical_milking = request.form.get('selected_period_for_analytical_milking')

    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cursor.execute(
        '''
            select * from (
                select
                    extract(month from date_recorded) as mon,
                    to_char(date_recorded,'Mon') as label_mon,
                    extract(year from date_recorded) as yyyy,
                    CAST(sum(amount/1000)AS integer) as total_amount
                    from milkings_per_day
                    where date_part('year', date_recorded) = {}
                    group by mon,yyyy, label_mon
                    order by extract(month from date_recorded) ASC
                )tbl1
                left join (
                select 
                    extract(month from date_recorded) as shipment_mon,
                    to_char(date_recorded,'Mon') as label_shipment_mon,
                    extract(year from date_recorded) as shipment_yyyy,
                    sum(amount) as shipment_total_amount
                    from shipments
                    group by shipment_mon,shipment_yyyy,label_shipment_mon
                    order by extract(month from date_recorded) ASC

                ) tbl2

                on tbl1.yyyy = tbl2.shipment_yyyy and tbl1.mon = tbl2.shipment_mon

        '''.format(selected_year)

    )
    milking_list = cursor.fetchall()

    milk_per_month = dict(month=[item['mon'] for item in milking_list],
                          amount=[int(0 if item['total_amount'] is None else item['total_amount'])
                                  for item in milking_list],
                          labels=[item['label_mon'] for item in milking_list])

    shipment_per_month = dict(month=[item['mon'] for item in milking_list],
                              amount=[int(0 if item['shipment_total_amount'] is None else item['shipment_total_amount'])
                                      for item in milking_list],
                              labels=[item['label_shipment_mon'] for item in milking_list])
    cursor.execute(
        '''
        SELECT milking_time,
            total_amount,
            ROUND((total_amount * 100 / SUM(total_amount) OVER ())::NUMERIC,2) AS percent_of_time
        FROM (
                SELECT milking_time,
                        SUM(amount) AS total_amount
                FROM milkings
                GROUP BY milking_time
            ) AS t
        ORDER BY percent_of_time DESC
        '''
    )
    percent_list = cursor.fetchall()
    percent_list = dict(milking_time=[item['milking_time'] for item in percent_list],
                        total_amount=[item['total_amount']
                                      for item in percent_list],
                        percent_of_time=[item['percent_of_time']
                                         for item in percent_list]
                        )

    cursor.execute('''
        SELECT 	distinct date_recorded, milking_time, ROUND((sum(total_amount)/1000)::NUMERIC,2) as total_amount      
        FROM (
                SELECT 
                date_recorded::DATE, 
                milking_time, 
                sum(amount) as total_amount
                FROM milkings
                where milking_period={}
                GROUP BY date_recorded, milking_time	
            ) AS t
            GROUP BY t.date_recorded, t.milking_time
            ORDER BY t.milking_time, t.date_recorded ASC
    '''.format(selected_period_for_analytical_milking)
    )

    milking_per_milking_time_and_date = cursor.fetchall()

    d = {'dates': [], 'evening': [], 'midday': [], 'morning': []}
    for i in range(len(milking_per_milking_time_and_date)):
        if milking_per_milking_time_and_date[i][0] not in d['dates']:
            d['dates'].append(milking_per_milking_time_and_date[i][0])
        if milking_per_milking_time_and_date[i][1] == 'EVENING':
            d['evening'].append(milking_per_milking_time_and_date[i][2])
        if milking_per_milking_time_and_date[i][1] == 'MIDDAY':
            d['midday'].append(milking_per_milking_time_and_date[i][2])
        if milking_per_milking_time_and_date[i][1] == 'MORNING':
            d['morning'].append(milking_per_milking_time_and_date[i][2])

    cursor.execute('''
        select milking_period,count(distinct animal_id),
        ROUND(sum(total_milk_up_to_today)/1000000::NUMERIC,2)
        from milkings 
        group by milking_period  
    ''')
    total_milk_progress_list = cursor.fetchall()

    total_milk_progress = dict(milking_period=[item[0] for item in total_milk_progress_list],
                        num_of_animals=[item[1]for item in total_milk_progress_list],
                        amount=[item[2] for item in total_milk_progress_list]
                        )

    milk_per_month = json.dumps(milk_per_month)
    milk_per_month = json.loads(milk_per_month)
    shipment_per_month = json.dumps(shipment_per_month)
    shipment_per_month = json.loads(shipment_per_month)
    percent_list = json.dumps(percent_list)
    percent_list = json.loads(percent_list)
    total_milk_progress = json.dumps(total_milk_progress)
    total_milk_progress = json.loads(total_milk_progress)

    return {
        'milk_per_month': milk_per_month,
        'shipment_per_month': shipment_per_month,
        'percent_list': percent_list,
        'milking_per_milking_time_and_date': d,
        'total_milk_progress': total_milk_progress
    }


@admin.route('/', methods=['GET', 'POST'])
@login_required
def list_data():

    years = db.session.query(extract(
        'year', MilkingPerDay.date_recorded).label('year')).distinct('year').all()
    years = [int(item['year']) for item in years]

    milking_periods = Milking.query.distinct(Milking.milking_period).all()
    milking_periods = [item.milking_period for item in milking_periods]

    return render_template('home/new_admin_v2.html',
                           years=years,
                           milking_periods=milking_periods,
                           title="Stable Data")

############### Incomes Graph Info ############################


@admin.route('/api/income', methods=['GET', 'POST'])
@login_required
def api_income():
    """
    Returns all income data
    """
    check_admin()

    # search filter
    search = request.form.get('income_year')

    income_query = income_per_month(search)
    expense_query = expense_per_month(search)
    check_income_vs_expense = income_vs_expense(search)

    return {
        'income_data': [income for income in income_query],
        'expense_data': [expense for expense in expense_query],
        'income_vs_expense': [amount for amount in check_income_vs_expense]
    }


##############################################################
##############################################################
################### Milking Views ############################
##############################################################
##############################################################


@admin.route('/milkings', methods=['GET', 'POST'])
@login_required
def list_milkings():
    """
    List all milkings
    """
    check_admin()

    list_of_dates = db.session.query(
        cast(Milking.date_recorded, Date).label('event_date')
    ).distinct(cast(Milking.date_recorded, Date)) \
        .order_by(cast(Milking.date_recorded, Date).desc())

    milkings = Milking.query\
        .order_by(Milking.date_recorded.desc())\
        .limit(24).\
        all()
    for item in milkings:
        if item.animal.status == False:
            milkings.remove(item)

    return render_template('home/milkings.html',
                           milkings=milkings,
                           list_of_dates=list_of_dates, title="Milkings")


@admin.route('/milkings/per_date', methods=['GET', 'POST'])
@login_required
def list_milkings_per_date():
    """
    List all milkings per given date
    """
    check_admin()

    if request.method == "POST":
        data = request.form.to_dict()

    milkings = Milking.query\
        .filter(func.date(Milking.date_recorded) == data['selected_day'])\
        .all()

    return render_template('home/milkings.html',
                           milkings_per_date=milkings,
                           title="Milkings")


@ admin.route('/milkings/per_animal', methods=['GET', 'POST'])
@ login_required
def list_milkings_per_animal():
    """
    List all milkings per given animal
    """
    check_admin()

    if request.method == "POST":
        data = request.form.to_dict()

    milkings = Milking.query\
        .filter_by(ear_tag=data['selected_animal'])\
        .all()

    return render_template('home/milkings.html',
                           milkings_per_animal=milkings, title="Milkings")


@ admin.route('/milkings/per_animal/<int:id>', methods=['GET', 'POST'])
@ login_required
def list_milkings_per_animal_id(id):
    """
    List all milkings per given animal
    """
    check_admin()

    milkings = Milking.query\
        .filter_by(animal_id=id)\
        .all()

    return render_template('home/milkings.html',
                           milkings_per_animal=milkings, title="Milkings")


@ admin.route('/milkings/statistics/<int:id>', methods=['GET', 'POST'])
@ login_required
def statistics(id):
    """
    List statistical data
    """
    check_admin()

    # Create an empty list in order for dict of results to get into.
    content = []
    # Get all milking_periods for animal
    periods = AnimalMilkingPeriods.query.distinct(
        AnimalMilkingPeriods.milking_period).all()
    periods = [item.milking_period for item in periods]

    return render_template('home/statistics.html', stat_results=content, id=id, periods=periods)


@ admin.route('/milkings/post_statistics/<int:id>', methods=['GET', 'POST'])
@ login_required
def post_statistics(id):
    # Create an empty list in order for dict of results to get into.
    content = []
    # Get all milking_periods for animal
    periods = AnimalMilkingPeriods.query.distinct(
        AnimalMilkingPeriods.milking_period).all()
    periods = [item.milking_period for item in periods]

    if request.method == 'POST':
        selected_period = request.form.get('selected_period')
        query = getMilkingData(id, selected_period)

    for item in query:
        stats = {
            "date_of_milking": item[0].strftime('%d-%m-%Y'),
            "total_sum": item[4],
            "total_avg": item[6],
            "animal_sum": item[1],
            "animal_percent": item[7],
            "animal_change": item[2],
            "milking_days": item[3]

        }
        content.append(stats)

    return jsonify(content)


def calculate_total_milk(last_milking, current_milking, rate, diff):
    percent = rate/diff
    total_sum = 0
    absolute_change = (last_milking + (last_milking*percent))-last_milking
    checked_milking = last_milking
    for i in range(1, diff):

        total_sum += checked_milking + absolute_change
        checked_milking = checked_milking + absolute_change
    total_sum += current_milking

    return total_sum


def calculate_total_milk_v2(last_milking, current_milking, rate, diff, start_date, end_date):
    d = {'total_amount': [],
         'day_recorded': [],
         'amount_recorded': []}

    percent = rate/diff
    total_sum = 0
    absolute_change = (last_milking + (last_milking*percent))-last_milking
    checked_milking = last_milking
    given_date = start_date

    for i in range(1, diff):

        total_sum += checked_milking + absolute_change
        checked_milking = checked_milking + absolute_change

        given_date = given_date + timedelta(days=1)
        d['day_recorded'].append(given_date)
        d['amount_recorded'].append(checked_milking)

    total_sum += current_milking
    d['total_amount'].append(total_sum)
    d['day_recorded'].append(end_date)
    d['amount_recorded'].append(current_milking)

    return d


def calculate_total_milk_v3(last_milking, current_milking, rate, diff, start_date, end_date):
    d = {'total_amount': [],
         'day_recorded': [],
         'amount_recorded': []}
    # Animal's first milking where date_of_birth > today
    if last_milking == 0 and rate == 0 and diff != 0:
        last_milking = math.ceil(current_milking - (current_milking * 0.2))
        rate = round(
                    (
                        (float(current_milking) -
                         last_milking)/last_milking
                    ), 3)

        percent = rate/diff
    # Animal's first milking where date_of_birth == today
    elif last_milking == 0 and rate == 0 and diff == 0:
        percent = 0

    # Animal's last milking where diff from today's milking == 0
    elif last_milking != 0 and diff != 0 and rate == 0:
        percent = rate/diff
    elif last_milking != 0 and diff == 0 and rate != 0:
        percent = rate
    elif last_milking != 0 and diff == 0 and rate == 0:
        percent = 0

    else:
        percent = rate/diff

    total_sum = 0
    absolute_change = (last_milking + (last_milking*percent))-last_milking
    checked_milking = last_milking
    given_date = start_date

    for i in range(1, diff):

        total_sum += int(checked_milking + absolute_change)
        checked_milking = int(checked_milking + absolute_change)

        given_date = given_date + timedelta(days=1)
        d['day_recorded'].append(given_date)
        d['amount_recorded'].append(checked_milking)

    total_sum += current_milking
    d['total_amount'].append(total_sum)
    d['day_recorded'].append(end_date)
    d['amount_recorded'].append(current_milking)

    return d

@ admin.route('/milkings/add', methods=['GET', 'POST'])
@ login_required
def add_milking():
    """
    Add a milking record to the database
    """
    check_admin()

    # make an empty integer in order for milking form to be able to put milking period when calls get_form_of_new_milking
    animal_id = int(float(0))

    add_milking = True

    # set this value in order for MilkingPerDay num_of_animals to increment by 1
    add_animal = 0
    now = datetime.now()
    form = MilkingForm()
    animals = Animal.query.filter(Animal.status == True)
    # Get last date on database in order for milkings to have same date if they are on the same week
    last_date_query = Milking.query.distinct(Milking.date_recorded).order_by(
        Milking.date_recorded.desc()).first()
    # Get only the date from the query
    last_date = last_date_query.date_recorded.date()

    # Combine last date and current time
    test_date = str(last_date)+' '+str(now.strftime("%H:%M:%S"))
    # Format final date in order to be ready for database
    final_date = datetime.strptime(test_date, "%Y-%m-%d %H:%M:%S")

    # List of animals in order for jinja form to evaluate that only correct ear_tags are going to be stored
    passed_animals = [int(item.ear_tag) for item in animals]

    # Get all milking dates from MilkingPerDay table
    milking_days = MilkingPerDay.query.distinct(
        MilkingPerDay.date_recorded).all()
    # Crete an updatable list of dates in order for new recorded to be added
    passed_days = [item.date_recorded for item in milking_days]
    #Define box that animal belongs to
    milking_box = 0

    my_list = []
    number_of_records_added = 0
    if request.method == "POST":
        form.box.data = 0
        # Get data from form and convert it to dict
        data = request.form.to_dict()
        # Remove empty values from the form
        data = {k: v for k, v in data.items() if v}

        for key in data.items():
            if "ear_tag" in key[0]:
                my_list.append(key[1])

            elif "amount" in key[0]:
                my_list.append(key[1])
            elif "box" in key[0]:
                if key[1] != '0':
                    milking_box = int(key[1])

        counter = len(my_list)

        for i in range(counter):
            # Ear tags are even numbers in list as it is impossible to pass amount without its
            if i == 0 or (i % 2) == 0:
                animal_id = Animal.query.filter_by(ear_tag=my_list[i]).first()
                if milking_box !=0:
                    
                    animal_id.animal_box = milking_box
                    db.session.commit()   

                if animal_id:
                    # Check what time sheep is milked
                    if final_date.hour >= 3 and final_date.hour < 12:
                        time_of_milking = 'MORNING'
                    elif final_date.hour >= 12 and final_date.hour <= 18:
                        time_of_milking = 'MIDDAY'
                    else:
                        time_of_milking = 'EVENING'
                    # Find last birth and add milking days to database
                    q = AnimalMilkingPeriods.query \
                        .filter(AnimalMilkingPeriods.animal_id == animal_id.id) \
                        .filter(AnimalMilkingPeriods.end_of_milking_period == None) \
                        .all()

                    # Check if animal has only one milking period
                    if len(q) != 0 and len(q) == 1:
                        # Differnce between birth date and milking date
                        d = date.today() - q[0].start_of_milking_period
                        milking_period = q[0].milking_period

                        # Get last milking
                        get_last_milking = db.session.query(
                            Milking.amount.label('amount'), cast(Milking.date_recorded, Date).label('dates')) \
                            .filter(Milking.animal_id == animal_id.id) \
                            .filter(Milking.milking_time == time_of_milking) \
                            .filter(Milking.milking_period == milking_period) \
                            .distinct(cast(Milking.date_recorded, Date)) \
                            .order_by(cast(Milking.date_recorded, Date).asc()) \
                            .all()
                        # In case animal has been milked again calculate percentange change
                        if len(get_last_milking) > 0:
                            amounts = [
                                item.amount for item in get_last_milking]
                            # Get all dates that animal has been milked
                            dates = [
                                item.dates for item in get_last_milking]
                            # Date of last milking
                            last_recorded_day = dates[-1]
                            # Get last milking to pass to calculate_total_milk function
                            last_milking = amounts[-1]
                            # Get change from last milking where there is one
                            change_from_last_milking = round(
                                (
                                    (float(my_list[i+1]) -
                                     last_milking)/last_milking
                                ), 3)
                            # Variables for full_details_function
                            diff_from_last_milking = (datetime.strptime(now.strftime(
                                "%Y/%m/%d %H:%M:%S"), '%Y/%m/%d %H:%M:%S').date() - last_recorded_day).days
                            start_date_for_full_details = last_recorded_day
                            end_date_for_full_details = datetime.strptime(now.strftime(
                                "%Y/%m/%d %H:%M:%S"), '%Y/%m/%d %H:%M:%S').date()
                        else:
                            # Set percentange change 0 when it is first time animal milked on each milking period
                            change_from_last_milking = 0
                            last_milking = 0
                            diff_from_last_milking = d.days
                            # Animal first time milked has diffence in days today - date_of_birth
                            start_date_for_full_details = q[0].start_of_milking_period

                            end_date_for_full_details = datetime.strptime(now.strftime(
                                "%Y/%m/%d %H:%M:%S"), '%Y/%m/%d %H:%M:%S').date()

                        # Check if date is on same week as the last recorded date
                        if last_date.isocalendar()[1] == now.date().isocalendar()[1]:
                            # Check what time sheep is milked
                            if final_date.hour >= 3 and final_date.hour < 12:
                                time_of_milking = 'MORNING'
                            elif final_date.hour >= 12 and final_date.hour <= 18:
                                time_of_milking = 'MIDDAY'
                            else:
                                time_of_milking = 'EVENING'
                            # If we are on same week change end_date to milking's date to prevent from adding extra days on milking_per_day table
                            end_date_for_full_details = final_date.date()
                            # Here we call calculate_total_milk_v3
                            full_details = calculate_total_milk_v3(
                                int(last_milking), int(my_list[i+1]), change_from_last_milking, diff_from_last_milking, start_date_for_full_details, end_date_for_full_details)
                            # Create milking instance
                            milking = Milking(ear_tag=my_list[i],
                                              amount=my_list[i+1],
                                              date_recorded=final_date,
                                              animal_id=animal_id.id,
                                              days_from_last_birth=(
                                                  final_date.date() - q[0].start_of_milking_period).days,
                                              milking_time=time_of_milking,
                                              milking_period=milking_period,
                                              change_from_last_milking=change_from_last_milking,
                                              total_milk_up_to_today=full_details['total_amount'][0]
                                              )
                            # loop all days from last milking up to today's
                            for i in range(len(full_details['day_recorded'])):
                                # If dates are passed to table for first time
                                if full_details['day_recorded'][i] not in passed_days:

                                    entry = MilkingPerDay(date_recorded=full_details['day_recorded'][i],
                                                          amount=full_details['amount_recorded'][i],
                                                          num_of_animals_milked=1
                                                          )

                                    db.session.add(entry)
                                    db.session.flush()
                                    db.session.commit()
                                    # Add day to list in order for the next ones to know that this day has been recorded
                                    passed_days.append(
                                        full_details['day_recorded'][i])
                                # If dates exist on databae
                                else:
                                    updated_date = MilkingPerDay.query.filter_by(
                                        date_recorded=full_details['day_recorded'][i]).first()
                                    updated_date.amount = updated_date.amount + \
                                        full_details['amount_recorded'][i]
                                    if updated_date.num_of_animals_milked == None:
                                        updated_date.num_of_animals_milked = 1
                                    else:
                                        updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                                    db.session.flush()
                                    db.session.commit()

                            try:
                                # add milking to the database
                                db.session.add(milking)
                                db.session.flush()
                                db.session.commit()
                                number_of_records_added += 1
                                if i > 1:
                                    continue

                            except:
                                db.session.rollback()
                                # in case milking name already exists
                                flash('Error: Η γαλακτομέτρηση για το ζώο με ενώτιο {} δεν αποθηκεύτηκε στη βάση.'.format(animal_id.ear_tag),
                                      category="danger")

                        # Milking is not on the same week
                        else:
                            # Check what time sheep is milked
                            if now.hour >= 3 and now.hour < 12:
                                time_of_milking = 'MORNING'
                            elif now.hour >= 12 and now.hour <= 18:
                                time_of_milking = 'MIDDAY'
                            else:
                                time_of_milking = 'EVENING'

                            # Check if query has results
                            if len(q) != 0 and len(q) == 1:
                                d = date.today() - q[0].start_of_milking_period
                                milking_period = q[0].milking_period

                                # Here we call calculate_total_milk_v3
                                full_details = calculate_total_milk_v3(
                                    int(last_milking), int(
                                        my_list[i + 1]), change_from_last_milking, diff_from_last_milking, start_date_for_full_details,
                                    end_date_for_full_details)

                                milking = Milking(ear_tag=my_list[i],
                                                  amount=my_list[i+1],
                                                  date_recorded=now.strftime(
                                    "%Y/%m/%d %H:%M:%S"),
                                    animal_id=animal_id.id,
                                    days_from_last_birth=d.days,
                                    milking_time=time_of_milking,
                                    milking_period=milking_period,
                                    change_from_last_milking=change_from_last_milking,
                                    total_milk_up_to_today=full_details['total_amount'][0]
                                )

                                for i in range(len(full_details['day_recorded'])):

                                    if full_details['day_recorded'][i] not in passed_days:

                                        entry = MilkingPerDay(date_recorded=full_details['day_recorded'][i],
                                                              amount=full_details['amount_recorded'][i],
                                                              num_of_animals_milked=1
                                                              )

                                        db.session.add(entry)
                                        db.session.flush()
                                        db.session.commit()

                                        passed_days.append(
                                            full_details['day_recorded'][i])
                                    else:
                                        updated_date = MilkingPerDay.query.filter_by(
                                            date_recorded=full_details['day_recorded'][i]).first()
                                        updated_date.amount = updated_date.amount + \
                                            full_details['amount_recorded'][i]
                                        updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                                        db.session.flush()
                                        db.session.commit()

                                try:
                                    # add milking to the database
                                    db.session.add(milking)
                                    db.session.flush()
                                    db.session.commit()
                                    number_of_records_added += 1
                                    if i > 1:
                                        continue

                                except Exception as error:
                                    db.session.rollback()
                                    # in case milking name already exists
                                    flash('Error: Κάτι πήγε στραβά.',
                                          category="danger")
                                    print(str(error.orig) +
                                          " for parameters" + str(error.params))

                    elif len(q) > 1:
                        flash('Error: Το ζώο με ενώτιο {} έχει ενεργές περισσότερες απο μια γαλακτικές περιόδους. Η εισαγωγή απέτυχε'.format(animal_id.ear_tag),
                              category="danger")
                    i += 1
                else:
                    if i > 1:
                        continue
                    else:
                        flash("Animal Ear Tag is invalid!!!", category="danger")
            else:
                i += 1
        flash('You have successfully added %d new records' % number_of_records_added,
              category="success")
    return render_template('home/milking.html', action="Add",
                           add_milking=add_milking, form=form,
                           animals=json.dumps(passed_animals),
                           animal_id=animal_id,
                           title="Add Milking")


def milking_has_been_changed(milkings_affected, position_of_changed_milking, milking_id, animal_id, old_amount, new_amount):
    ########### if there are more than one milkings ###############

    # Milking that has been changed
    changed_milking = Milking.query.get_or_404(milking_id)

    # Get new query as values on milking table have been updated
    new_milkings_affected = Milking.query \
        .filter(Milking.animal_id == animal_id) \
        .filter(Milking.milking_time == changed_milking.milking_time) \
        .order_by(Milking.id) \
        .all()

    # Get all animal's milkings based on time it has been milked that has been passed to function
    milkings_affected = milkings_affected
    # Find the position of milking that has been updated in order to get previous milking and all next ones
    # [0,1,2,3,4] [0]
    position_of_changed_milking = position_of_changed_milking

    for i in range(position_of_changed_milking, len(milkings_affected)):

        # We are in the first recorded milking meaning there is no previous data
        if i == 0:
            last_milking = 0
            current_milking = milkings_affected[i]['amount']
            rate = 0
            diff = int(milkings_affected[i]['days_from_last_birth'])
            start_date = datetime.strptime(
                milkings_affected[i]['date_recorded'], '%Y-%m-%d').date() - timedelta(days=int(diff))
            end_date = datetime.strptime(
                milkings_affected[i]['date_recorded'], '%Y-%m-%d').date()

        # we are not in the first milking meaning that there is at least a previous one
        else:
            last_milking = milkings_affected[i-1]['amount']
            current_milking = milkings_affected[i]['amount']
            rate = milkings_affected[i]['change_from_last_milking']
            diff = (datetime.strptime(milkings_affected[i]['date_recorded'], '%Y-%m-%d').date() -
                    datetime.strptime(milkings_affected[i-1]['date_recorded'], '%Y-%m-%d').date()).days
            start_date = datetime.strptime(
                milkings_affected[i-1]['date_recorded'], '%Y-%m-%d').date()
            end_date = datetime.strptime(
                milkings_affected[i]['date_recorded'], '%Y-%m-%d').date()

        # Step 1 calculate amounts for days based on original state - from milking changed step -1
        # It returns a dict containg -- total_amount, day_recorded and recorded_amounts
        before_update = calculate_total_milk_v3(last_milking=last_milking,
                                                current_milking=current_milking,
                                                rate=rate,
                                                diff=diff,
                                                start_date=start_date,
                                                end_date=end_date
                                                )
        print(before_update)
        if i == position_of_changed_milking and i != 0:

            # Step 2 calculate new rate based on new_amount
            new_rate = (new_amount - milkings_affected[position_of_changed_milking -
                        1]['amount']) / milkings_affected[position_of_changed_milking - 1]['amount']
            # Calculate new total milk stats based on new amount and new rate -- diff is the same as date hasn't changed
            after_update = calculate_total_milk_v3(last_milking=milkings_affected[position_of_changed_milking-1]['amount'],
                                                   current_milking=new_amount,
                                                   rate=new_rate,
                                                   diff=(datetime.strptime(milkings_affected[i]['date_recorded'], '%Y-%m-%d') -
                                                         datetime.strptime(milkings_affected[i-1]['date_recorded'], '%Y-%m-%d')).days,
                                                   start_date=datetime.strptime(
                                                       milkings_affected[i-1]['date_recorded'], '%Y-%m-%d'),
                                                   end_date=datetime.strptime(
                                                       milkings_affected[i]['date_recorded'], '%Y-%m-%d')
                                                   )
            print(after_update)
        elif i == position_of_changed_milking and i == 0:
            new_rate = 0
            last_milking = 0
            after_update = calculate_total_milk_v3(last_milking=last_milking,
                                                   current_milking=new_amount,
                                                   rate=new_rate,
                                                   diff=diff,
                                                   start_date=start_date,
                                                   end_date=end_date
                                                   )
            print(after_update)
        else:

            new_rate = (
                new_milkings_affected[i].amount - new_milkings_affected[i-1].amount) / new_milkings_affected[i-1].amount

            after_update = calculate_total_milk_v3(new_milkings_affected[i-1].amount, new_milkings_affected[i].amount,
                                                   new_rate,
                                                   (int((new_milkings_affected[i].date_recorded.date(
                                                   ) - new_milkings_affected[i-1].date_recorded.date()).days)),
                                                   new_milkings_affected[i-1].date_recorded.date(
            ), new_milkings_affected[i].date_recorded.date()
            )
            print(after_update)

        # Get records of MilkingPerDay table that are affected one milking prior to the updated one
        milk_per_days = MilkingPerDay.query.filter(and_(
            MilkingPerDay.date_recorded >= before_update['day_recorded'][0],
            MilkingPerDay.date_recorded <= before_update['day_recorded'][-1])) \
            .order_by(MilkingPerDay.date_recorded.asc()) \
            .all()

        # Subtract old amounts from database
        for j in range(len(milk_per_days)):
            try:
                milk_per_days[j].amount = milk_per_days[j].amount - \
                    before_update['amount_recorded'][j]
                db.session.flush()
                db.session.commit()
                milk_per_days[j].amount = milk_per_days[j].amount + \
                    after_update['amount_recorded'][j]
                db.session.flush()
                db.session.commit()
                failed = False
            except Exception as e:
                # log your exception in the way you want -> log to file, log as error with default logging, send by email. It's upon you
                print('---------------- MilkingPerDay', e)
                db.session.rollback()
                db.session.flush()  # for resetting non-commited .add()
                failed = True

        # Step 3 calculate fields need changing on Milking table -- for the milking that has been updated
        try:
            if i != 0:
                new_milkings_affected[i].change_from_last_milking = (
                    after_update['amount_recorded'][-1] - new_milkings_affected[i - 1].amount) / new_milkings_affected[i-1].amount
                new_milkings_affected[i].total_milk_up_to_today = after_update['total_amount'][0]
                db.session.flush()
                db.session.commit()
                failed = False
            else:
                new_milkings_affected[i].total_milk_up_to_today = after_update['total_amount'][0]
                db.session.flush()
                db.session.commit()
                failed = False

        except Exception as e:
            # log your exception in the way you want -> log to file, log as error with default logging, send by email. It's upon you
            db.session.rollback()
            db.session.flush()  # for resetting non-commited .add()
            failed = True


    return failed


@ admin.route('/milkings/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_milking(id):
    """
    Edit a milking record
    """
    check_admin()

    add_milking = False

    milking = Milking.query.get_or_404(id)
    old_amount = milking.amount
    parsed_ear_tag = milking.ear_tag
    parsed_amount = milking.amount
    parsed_date = milking.date_recorded

    # Get all animal's milkings based on time it has been milked
    milkings_affected = Milking.query \
        .filter(Milking.animal_id == milking.animal_id) \
        .filter(Milking.milking_time == milking.milking_time) \
        .order_by(Milking.id) \
        .all()

    position_of_changed_milking = milkings_affected.index(milking)

    dict_of_milkings_affected = [item.to_dict() for item in milkings_affected]

    form = MilkingForm(obj=milking)
    if form.validate_on_submit():
        milking.ear_tag = form.ear_tag.data
        milking.amount = form.amount.data

        # first call the has_been_changed function and then commit the change of milking
        x = milking_has_been_changed(dict_of_milkings_affected, position_of_changed_milking,
                                     milking.id, milking.animal_id, old_amount, milking.amount)
        if x == False:
            db.session.flush()
            db.session.commit()

            flash('Επιτυχής επεξεργασία γαλακτομέτρησης.', 'success')
            return redirect(url_for('admin.list_milkings'))

        else:
            flash('Δεν έγινε αλλαγή της γαλακτομέτρησης επειδή προέκυψε σφάλμα στην επεξεργασία των δεδομένων.', 'danger')

            # redirect to the departments page
            return redirect(url_for('admin.list_milkings'))

    form.ear_tag.data = milking.ear_tag
    form.amount.data = milking.amount
    return render_template('home/milking.html', action="Edit",
                           add_milking=add_milking, form=form,
                           milking=milking,
                           parsed_ear_tag=parsed_ear_tag,
                           parsed_amount=parsed_amount,
                           parsed_date=parsed_date,
                           title="Edit Milking")


@ admin.route('/milkings/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_milking(id):
    """
    Delete a milking from the database
    """
    check_admin()
    # Get milking to be deleted
    milking = Milking.query.get_or_404(id)
    # Get all affected milkings from the deleted one
    milkings_affected = Milking.query \
        .filter(Milking.animal_id == milking.animal_id) \
        .filter(Milking.milking_time == milking.milking_time) \
        .order_by(Milking.id) \
        .all()
    if len(milkings_affected) > 1:
        before_update = calculate_total_milk_v3(last_milking=milkings_affected[-2].amount,
                                                current_milking=milkings_affected[-1].amount,
                                                rate=milkings_affected[-1].change_from_last_milking,
                                                diff=milkings_affected[-1].days_from_last_birth -
                                                milkings_affected[-2].days_from_last_birth,
                                                start_date=milkings_affected[-2].date_recorded.date(
        ),
            end_date=milkings_affected[-1].date_recorded.date(
        )
        )
    else:
        before_update = calculate_total_milk_v3(last_milking=0,
                                                current_milking=milkings_affected[-1].amount,
                                                rate=0,
                                                diff=milkings_affected[-1].days_from_last_birth,
                                                start_date=milkings_affected[-1].date_recorded.date() - timedelta(
                                                    days=int(milkings_affected[-1].days_from_last_birth)),
                                                end_date=milkings_affected[-1].date_recorded.date(
                                                )
                                                )

    # Allow only last milking to be deleted
    if milkings_affected[-1] != milking:
        flash('Δεν έγινε διαγραφή της γαλακτομέτρησης επειδή δεν έιναι η τελευταία καταχωρημένη γαλακτομέτρηση ' +
              'για την συγκεκριμένη χρονική στιγμή της ημέρας. ' +
              'Οι επόμενες γαλακτομετρήσεις είναι συνδεδεμένες με αυτή και τα ποσοστά τους υπολογίστηκαν βάση αυτής. ' +
              'Μπορείτε να αλλάξετε την ποσότητα της με το Edit και να την βάλετε ίση με μηδέν ' +
              'εαν δεν θέλετε να υπολογιστεί στον συνολικό πίνακα γάλακτος της μονάδας.', 'danger')
        return redirect(url_for('admin.list_milkings_per_animal_id', id=milking.animal_id))

    else:

        if len(before_update['day_recorded']) > 1:
            for i in range(len(before_update['day_recorded'])):
                query_date = MilkingPerDay.query.filter(
                    MilkingPerDay.date_recorded == before_update['day_recorded'][i]).first()
                query_date.amount = query_date.amount - \
                    before_update['amount_recorded'][i]
                query_date.num_of_animals_milked = query_date.num_of_animals_milked - 1
                db.session.flush()
                db.session.commit()
            db.session.delete(milking)
            db.session.flush()
            db.session.commit()
            flash('Επιτυχής διαγραφή γαλακτομέτρησης.', 'success')
            # redirect to the milkings page
            return redirect(url_for('admin.list_milkings'))

        else:
            query_date = MilkingPerDay.query.filter(
                MilkingPerDay.date_recorded == milkings_affected[-1].date_recorded.date()).first()
            query_date.amount = query_date.amount - \
                milkings_affected[-1].amount
            query_date.num_of_animals_milked = query_date.num_of_animals_milked - 1
            db.session.flush()
            db.session.commit()
            db.session.delete(milking)
            db.session.flush()
            db.session.commit()
            flash('Επιτυχής διαγραφή γαλακτομέτρησης.', 'success')
            # redirect to the milkings page
            return redirect(url_for('admin.list_milkings'))

    return render_template(title="Delete Milking")

@ admin.route('/milkings/stop_period/', methods=['GET', 'POST'])
@ login_required
def stop_period():
    """
    Add stop date to the AnimalMilkingPeriods Table
    """
    check_admin()

    now = datetime.now()
    form = StopMilkingForm()
    animals = Animal.query.filter(Animal.status == True)
    # List of animals in order for jinja form to evaluate that only correct ear_tags are going to be stored
    passed_animals = [int(item.ear_tag) for item in animals]

    my_list = []
    number_of_records_added = 0
    if request.method == "POST":
        # Get data from form and convert it to dict
        data = request.form.to_dict()
        # Remove empty values from the form
        data = {k: v for k, v in data.items() if v}

        for key in data.items():
            if "ear_tag" in key[0]:
                my_list.append(key[1])

        counter = len(my_list)

        for i in range(counter):
            
            animal_id = Animal.query.filter_by(ear_tag=my_list[i]).first()

            if animal_id:
                stop_milking_period = AnimalMilkingPeriods.query\
                                            .filter(AnimalMilkingPeriods.animal_id==animal_id.id)\
                                            .filter(AnimalMilkingPeriods.end_of_milking_period==None)\
                                            .order_by(AnimalMilkingPeriods.start_of_milking_period.desc())\
                                            .first()
                stop_milking_period.end_of_milking_period=now.strftime("%Y/%m/%d")
    
                try:
                    # stop milking from the database
                    db.session.flush()
                    db.session.commit()
                    number_of_records_added += 1
                    if i > 1:
                        continue

                except Exception as e:
                    db.session.rollback()
                    # in case milking name already exists
                    print('---------------', e)
                    flash('Error: Το τέλος γαλακτομέτρησης για το ζώο με ενώτιο {} δεν αποθηκεύτηκε στη βάση.'.format(animal_id.ear_tag),
                            category="danger")
        flash('Επιτυχής εισαγωγή τέλους γλακτομέτρησης {} ζώων!!!'.format(number_of_records_added), category="success")
                
    return render_template('home/stop_milking.html', action="Add",
                           form=form,
                           animals=json.dumps(passed_animals),
                           
                           title="Stop Milking")


##########################################################################
##########################################################################
#################### Animal Views ########################################
##########################################################################
##########################################################################

@ admin.route('/animals', methods=['GET', 'POST'])
@ login_required
def list_animals():
    """
    List all animals
    """
    check_admin()
    animals = Animal.query
    alert_query = Alert.query.distinct(Alert.name).all()
    animal_status = True
    return render_template('home/animals.html',
                           animals=animals,
                           animal_status=animal_status,
                           alerts=alert_query, title="animals")


@ admin.route('/animals/inactive', methods=['GET', 'POST'])
@ login_required
def list_inactive_animals():
    """
    List all inactive animals
    """
    check_admin()
    animals = Animal.query
    animal_status = False
    return render_template('home/inactive_animals.html',
                           animals=animals, animal_status=animal_status, title="animals")


@ admin.route('/animals/per_birth_date', methods=['GET', 'POST'])
@ login_required
def list_animal_per_birth_date():
    """
    List all animals per given date
    """
    check_admin()

    if request.method == "POST":
        data = request.form.to_dict()
    # check_parents = []
    parents = []
    # animals = Animal.query\
    #     .filter(Animal.date_of_birth.between(data['start_date'], data['end_date']))\
    #     .all()

    # for item in animals:
    #     parent = AnimalBirth.query.filter_by(child_id=item.id).first()
    #     if parent:
    #         if parent.parent.id not in check_parents:
    #             check_parents.append(parent.parent.id)
    #             parents.append(parent)
    #         else:
    #             continue
    #     else:
    #         continue

    animals = AnimalMilkingPeriods.query\
                .filter(AnimalMilkingPeriods.start_of_milking_period.between(data['start_date'], data['end_date']))\
                .all()
    for item in animals:
        
        ear_tag = Animal.query.filter(Animal.id == item.animal_id).first()

        d = dict(animal_id = item.animal_id,
        ear_tag=ear_tag.ear_tag,
        date = item.start_of_milking_period,
        has_child = item.has_child)
        parents.append(d)

    alert_query = Alert.query.distinct(Alert.name).all()

    return render_template('home/animal_per_birth_date.html',
                           animals=animals,
                           parents=parents,
                           alerts=alert_query, title="Animals")


@ admin.route('/animals/per_alert/<int:alert>', methods=['GET', 'POST'])
def per_alert(alert):

    # Take all Alerts records based on alert id
    first_query = AnimalAlert.query.filter(AnimalAlert.alert_id == alert).all()

    # Create an empty list
    list_of_animals_in_first_query = []

    # Add all animal records based on id in the list in order to query further...
    for item in first_query:
        list_of_animals_in_first_query.append(item.animal_id)

    # Query animal table based on animals having the specific alert
    query = Animal.query.filter(
        Animal.id.in_(list_of_animals_in_first_query))

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            cast(Animal.ear_tag, String).ilike(f'%{search}%')
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['id', 'ear_Tag', 'date_of_birth']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(Animal, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [animal.to_dict() for animal in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': Animal.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@ admin.route('/animals/per_alert_view', methods=['GET', 'POST'])
def animals_per_alert_view():
    check_admin()
    animals = Animal.query
    if request.method == "POST":
        data = request.form.get('alertSelect')

    alert_id = data

    alert_query = Alert.query.distinct(Alert.name).all()

    return render_template('home/animal_per_alert.html', animals=animals, alert_id=alert_id, alerts=alert_query)


@ admin.route('/api/data/<status>', methods=['GET', 'POST'])
def data(status):

    query = Animal.query.filter(Animal.status == status)

    # search filter
    search = request.args.get('search[value]')
    if search:
        query = query.filter(db.or_(
            cast(Animal.ear_tag, String).ilike(f'%{search}%')
        ))
    total_filtered = query.count()

    # sorting
    order = []
    i = 0
    while True:
        col_index = request.args.get(f'order[{i}][column]')
        if col_index is None:
            break
        col_name = request.args.get(f'columns[{col_index}][data]')
        if col_name not in ['id', 'ear_Tag', 'date_of_birth']:
            col_name = 'id'
        descending = request.args.get(f'order[{i}][dir]') == 'desc'
        col = getattr(Animal, col_name)
        if descending:
            col = col.desc()
        order.append(col)
        i += 1
    if order:
        query = query.order_by(*order)

    # pagination
    start = request.args.get('start', type=int)
    length = request.args.get('length', type=int)
    query = query.offset(start).limit(length)

    # response
    return {
        'data': [animal.to_dict() for animal in query],
        'recordsFiltered': total_filtered,
        'recordsTotal': Animal.query.count(),
        'draw': request.args.get('draw', type=int),
    }


@ admin.route('/animals/add', methods=['GET', 'POST'])
@ login_required
def add_animal():
    """
    Add an animal record to the database
    """
    check_admin()

    add_animal = True
    now = datetime.now()
    form = AnimalForm()
    if form.validate_on_submit():
        # If parent tag in form check whether parent exists on database or not
        if form.parent_ear_tag.data != None:
            # Get parent that is passed from form
            query_parent = Animal.query.filter_by(
                ear_tag=form.parent_ear_tag.data).first()
            # If tag on form is incorrect flash message and redirect
            if not query_parent:
                add_animal = False
                flash('Error: Το ενώτιο του γονέα δεν υπάρχει στη βάση.\n \
                Εάν θέλετε να εισάγετε γονέα τότε βάλτε σωστό ενώτιο. \n \
                Αλλίως δημιουργήστε ζώο χωρίς γονέα.',
                      category="danger")
                # Redirect to add new animal page
                return redirect(url_for('admin.add_animal'))
            elif query_parent:
                q = AnimalMilkingPeriods.query \
                    .filter(AnimalMilkingPeriods.animal_id == query_parent.id) \
                    .filter(AnimalMilkingPeriods.end_of_milking_period == None) \
                    .all()
                # Child cannot be given birth prior to parent's date of birth
                if form.date_of_birth.data < query_parent.date_of_birth:
                    flash(
                        'Η ημερομηνία γέννησης του ζώου είναι μικρότερη απο αυτή του γονέα. Το ζώο δεν δημιουργήθηκε', category="danger")
                    query_parent = False
                    # Redirect to add new animal page
                    return redirect(url_for('admin.add_animal'))
                # If it is parent's first birth
                if len(q) == 0 and form.date_of_birth.data < query_parent.date_of_birth:
                    add_animal = True
                    query_parent = True

                elif len(q) > 0 and form.date_of_birth.data != q[0].start_of_milking_period:
                    flash(
                        '''Ο γονέας έχει ενεργή γαλακτική περίοδο.
                           Το ζώο που δημιουργείται δεν έχει την ίδια ημερομηνια γέννησης με την αρχή της γαλακτικής περιόδου που είναι ενεργή.
                           Συνεπώς δεν μπορεί να εισαχθεί νέα γέννα.
                           Η μόνη περίπτωση που επιτρέπεται είναι το ζώο να γεννήσει δίδυμα.
                           Αυτό σημαίνει πως το νέο ζώο θα πρέπει να έχει την ίδια ημερομηνία με το αδερφάκι του!!!
                           Ελέγξτε στην καρτέλα του ζώου την ημερομηνία αρχής της ενεργής γαλακτικής περιόδου.
                           Αυτή πρέπει να συμπίπτει με την ημερμονία γέννησης ενός παιδιού.''', category="danger")
                    query_parent = False
                    # Redirect to add new animal page
                    return redirect(url_for('admin.add_animal'))

        # Otherwise set parent to False in order function auto_link_birth not to be executed
        else:
            query_parent = False

        # Create animal instance and add to database
        animal = Animal(ear_tag=form.ear_tag.data,
                        date_of_birth=form.date_of_birth.data
                        )
        if add_animal:
            try:
                # add animal to the database
                db.session.add(animal)
                db.session.commit()
                flash('Επιτυχής δημιουργία νέου ζώου.', category="success")

            except:
                # in case animal tag already exists
                flash('Error: Το ενώτιο του ζώου υπάρχει ήδη στη βάση.',
                      category="danger")

        # If parent exists get its child and link birth along with correct milkng period
        if(query_parent):
            query_child = Animal.query.filter_by(
                ear_tag=form.ear_tag.data).first()

            auto_link_birth(query_parent.id, query_child.id)
            flash('Επιτυχής σύνδεση με γονέα.',
                  category="success")
            # Redirect to add new animal page
            return redirect(url_for('admin.add_animal'))

    # load aniamal template
    return render_template('home/animal.html', action="Add",
                           add_animal=add_animal, form=form,
                           title="Add Animal")


@ admin.route('/animals/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_animal(id):
    """
    Edit an Animal
    """
    check_admin()

    add_animal = False

    animal = Animal.query.get_or_404(id)
    form = AnimalForm(obj=animal)
    if form.validate_on_submit():

        # Get animal that changes birth
        animal_changes_birth = Animal.query.filter_by(id=id).first()
        # Get birth instance of animal where its role is child as we are interested in ewe's milkings
        births = AnimalBirth.query.filter_by(child_id=id).all()
        # Make sure all is correct
        if len(births) == 1:
            # as we are interested in ewe's milkings
            mother = Animal.query.filter_by(id=births[0].parent_id).first()
        # This should be retrieved before child changes its birth
        mothers_milking_period = AnimalMilkingPeriods.query.filter(
            AnimalMilkingPeriods.start_of_milking_period == animal_changes_birth.date_of_birth).first()
        # Get mother's milking periods that are to be changed according to which milking period changes
        mothers_milkings_based_on_period_that_changes = Milking.query \
            .filter(Milking.animal_id == mother.id) \
            .filter(Milking.milking_period == mothers_milking_period.milking_period).all()
        # Here's changes happen
        animal.ear_tag = form.ear_tag.data
        animal.date_of_birth = form.date_of_birth.data
        mothers_milking_period.start_of_milking_period = form.date_of_birth.data
        db.session.commit()

        for item in mothers_milkings_based_on_period_that_changes:
            item.days_from_last_birth = (
                item.date_recorded.date() - form.date_of_birth.data).days
            db.session.commit()

        flash('Η ημερομηνία γέννησης του ζώου ανανεώθηκε!!!', category='success')
        # redirect to the animal page
        return redirect(url_for('admin.list_animals'))

    form.ear_tag.data = animal.ear_tag
    form.date_of_birth.data = animal.date_of_birth
    return render_template('home/animal.html', action="Edit",
                           add_animal=add_animal, form=form,
                           animal=animal, title="Edit Animal")


@ admin.route('/animals/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_animal(id):
    """
    Delete an animal from the database
    """
    check_admin()

    animal = Animal.query.get_or_404(id)
    animal.status = False
    db.session.commit()
    flash('You have successfully deleted the animal.')

    # redirect to the animals page
    return redirect(url_for('admin.list_animals'))

    return render_template(title="Delete Animal")


@ admin.route('/animals/reactivate/<int:id>', methods=['GET', 'POST'])
@ login_required
def reactivate_animal(id):
    """
    Reactivate an animal on the database
    """
    check_admin()

    animal = Animal.query.get_or_404(id)
    animal.status = True
    db.session.commit()
    flash('Επιτυχής ενεργοποίηση του ζώου.', category='success')

    # redirect to the animals page
    return redirect(url_for('admin.list_animals'))

    return render_template(title="Reactivate Animal")

##########################################################################
##########################################################################
#################### Alert Views ########################################
##########################################################################
##########################################################################


@ admin.route('/alerts', methods=['GET', 'POST'])
@ login_required
def list_alerts():
    """
    List all alerts
    """
    check_admin()

    alerts = Alert.query.all()

    return render_template('home/alerts.html',
                           alerts=alerts, title="Alerts")


@ admin.route('/alerts/add', methods=['GET', 'POST'])
@ login_required
def add_alert():
    """
    Add an alert record to the database
    """
    check_admin()

    add_alert = True
    form = AlertForm()
    if form.validate_on_submit():
        alert = Alert(name=form.name.data
                      )
        try:
            # add alert to the database
            db.session.add(alert)
            db.session.commit()
            flash('You have successfully added a new alert.')
        except:
            # in case animal tag already exists
            flash('Error: Alert name already exists.')

        # redirect to departments page
        return redirect(url_for('admin.add_alert'))

    # load department template
    return render_template('home/alert.html', action="Add",
                           add_alert=add_alert, form=form,
                           title="Add Alert")


@ admin.route('/alerts/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_alert(id):
    """
    Edit an Alert
    """
    check_admin()

    add_alert = False

    alert = Alert.query.get_or_404(id)
    form = AlertForm(obj=alert)
    if form.validate_on_submit():
        alert.name = form.name.data
        db.session.commit()
        flash('Επιτυχής τροποποίηση της ειδοποίησης.', category='success')

        # redirect to the alert page
        return redirect(url_for('admin.list_alerts'))

    form.name.data = alert.name
    return render_template('home/alert.html', action="Edit",
                           add_alert=add_alert, form=form,
                           title="Edit Alert")


@ admin.route('/alerts/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_alert(id):
    """
    Delete an alert from the database
    """
    check_admin()
    alert = Alert.query.get_or_404(id)
    db.session.delete(alert)
    db.session.commit()

    flash('Επιτυχής διαγραφή της ειδοποίησης.', category='success')

    # redirect to the alerts page
    return redirect(url_for('admin.list_alerts'))

    return render_template(title="Delete Alert")


@ admin.route('/alerts/delete_animal_alert/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_animal_alert(id):
    """
    Delete an animal alert from the database
    """
    check_admin()

    alert = AnimalAlert.query.get_or_404(id)
    db.session.delete(alert)
    db.session.commit()

    flash('Επιτυχής διαγραφή της ειδοποίησης.', category='success')

    # redirect to the animals page
    return redirect(url_for('admin.animal_card', id=alert.animal_id))

    return render_template(title="Delete Animal")

# Section to link alerts with animals ############################################3


@ admin.route('/alerts/link/<int:id>', methods=['GET', 'POST'])
@ login_required
def link_alert(id):
    """
    Add a relationship to Animal-Alerts table
    """
    check_admin()
    animal = Animal.query.get_or_404(id)
    link_alert = True
    form = AnimalAlertForm()
    if form.validate_on_submit():
        link_alert = AnimalAlert(animal_id=animal.id,
                                 alert_id=form.data['alert'].id,
                                 date_recorded=form.date_recorded.data
                                 )

        try:
            # add alert to the database
            db.session.add(link_alert)
            db.session.commit()
            flash('Επιτυχής εισαγωγή ειδοποίησης.', category='success')
        except:
            # in case alert already exists
            flash('Κάτι πήγε στράβα.', category='danger')

        # redirect to alert page
        return redirect(url_for('admin.list_animals'))

    # load alert template
    return render_template('home/link_alert.html', action="Add",
                           link_alert=link_alert, form=form,
                           animal=animal,
                           title="Link Alert")

#####################################################################
#####################################################################
################## Animal Cards #####################################
#####################################################################
#####################################################################


@ admin.route('/animal/card/<int:id>', methods=['GET', 'POST'])
@ login_required
def animal_card(id):
    """
    Display all animal info
    """
    check_admin()
    number_of_milkings = 0
    animal = Animal.query.get_or_404(id)
    milking = Milking.query.filter_by(animal_id=animal.id, milking_period=1)
    alert = AnimalAlert.query.filter_by(animal_id=animal.id)
    children = AnimalBirth.query.filter_by(parent_id=animal.id)
    parent = AnimalBirth.query.filter_by(child_id=animal.id).first()
    year_query = db.session.query(extract('year', Milking.date_recorded).label('year'))\
        .filter(Milking.animal_id == id).distinct().order_by(asc('year'))
    current_milking_period = AnimalMilkingPeriods.query.filter_by(animal_id=animal.id, end_of_milking_period=None).all()
    
    q = db.session.query(
        Milking.milking_period,
        func.sum(Milking.amount).label('recorded_amount'),
        func.sum(Milking.total_milk_up_to_today).label('estimated_amount'),
        func.max(Milking.days_from_last_birth).label('milked_days')) \
        .filter(Milking.animal_id == id) \
        .group_by(Milking.milking_period) \
        .order_by(Milking.milking_period.asc()) \
        .all()

    stats = dict(periods=[], recorded_amounts=[],
                 estimated_amounts=[], milked_days=[])
    for i in range(len(q)):
        stats['periods'].append(q[i][0])
        stats['recorded_amounts'].append(round((q[i][1]/1000), 2))
        stats['estimated_amounts'].append(round((q[i][2]/1000), 2))
        stats['milked_days'].append(q[i][3])

    for item in milking:
        number_of_milkings += 1  # Get total number of milkings

    # Create empty dict to pass all animal details
    animal_card = {"milkings": [], "alerts": [],
                   "children": [], "children_birth": [],
                   "birth_id": [],
                   "children_id": [], "parent_id": [],
                   "stats": [], "last_birth":[],
                   "animal_box":''
                   }
    animal_card['animal_box'] = animal.animal_box

    if parent:
        parent_id = parent.parent.id
        parent_tag = parent.parent.ear_tag

    else:
        parent_tag = ''
        parent_id = ''

    animal_card['id'] = animal.id
    animal_card['ear_tag'] = animal.ear_tag
    animal_card['date_of_birth'] = Animal.query.filter_by(
        ear_tag=animal.ear_tag).one().date_of_birth.strftime("%Y/%m/%d")
    
    last_birth = AnimalMilkingPeriods.query\
                                .filter(AnimalMilkingPeriods.animal_id == id,AnimalMilkingPeriods.end_of_milking_period == None)\
                                .order_by(AnimalMilkingPeriods.start_of_milking_period.desc())\
                                .all()
    if len(last_birth) > 1:
        animal_card['last_birth'] = 'Πολλαπλές Ενεργές Γέννες'
    elif len(last_birth) == 1:
        animal_card['last_birth'] = last_birth[0].start_of_milking_period.strftime("%d-%m-%Y")
    elif len(last_birth) == 0:
        animal_card['last_birth'] = 'Δεν υπάρχει ενεργή γέννα.'


    for item in milking:
        # Create a list with all milkings whatever the year.
        animal_card['milkings'].append(item.amount)

    milking_stats = getMilkingData(
        animal_id=id, selected_year=date.today().year)  # send request to database that receives milking amounts per month for current year as starting point.

    for item in alert:
        # In case not all alerts have date_recorded
        if item.date_recorded:
            date_recorded = item.date_recorded.strftime("%d/%m/%Y")
        else:
            date_recorded = ''
        result = {'id': item.id,
                  'animal_id': item.animal_id,
                  'alert': item.alert_id_alert.name,
                  'date': date_recorded}
        # get all alerts if they exist.
        animal_card['alerts'].append(result)

     # Check if animal exists in database
    if animal.status == False:
        # Animals are not deleted from database, they take status False if they are dead.
        inactive_animal = True
    else:
        inactive_animal = False

    # Get all data for all children that animal gave birth to.
    for item in children:
        animal_card['children'].append(item.child.ear_tag)
        animal_card['children_birth'].append(item.child.date_of_birth.strftime(
            "%Y/%m/%d"))
        animal_card['children_id'].append(item.child.id)
        animal_card["birth_id"].append(item.id)

    # pass the number of milkings to dict.
    animal_card['number_of_milkings'] = number_of_milkings

    result = json.dumps(animal_card)
    result = json.loads(result)

    return render_template('home/animal_card.html', action="Add",
                           result=result,
                           milking_stats=milking_stats,
                           parent_id=parent_id,
                           parent_tag=parent_tag,
                           years=year_query,
                           inactive_animal=inactive_animal,
                           milking_periods=[
                               item for item in animal.set_milking_period],
                           stats=stats,
                           current_milking_period=current_milking_period,
                           title="Animal Card")


################################################################
################################################################
##############  Birth Section ##################################
################################################################

@ admin.route('/birth/<int:id>', methods=['GET', 'POST'])
@ login_required
def link_birth(id):
    """
    Add a relationship to Animal-Births table
    """
    check_admin()
    # Get parent
    parent = Animal.query.get_or_404(id)

    # A list in descending order containg all births from AnimalMilkingPeriods table
    get_births = AnimalMilkingPeriods.query \
        .filter(AnimalMilkingPeriods.animal_id == parent.id) \
        .order_by(AnimalMilkingPeriods.start_of_milking_period.desc()) \
        .all()

    link_birth = True
    form = ParentForm()
    if form.validate_on_submit():
        child_id = Animal.query.filter_by(ear_tag=form.child.data).first()
        # if there are no births start milking period from number one
        if not get_births:
            add_milking_period = True
            my_message = 'Επιτυχής εισαγωγή εγγραφής στον πίνακα γαλακτικών περιόδων'
            # Query to get last milking period that is active
            q = AnimalMilkingPeriods.query.distinct(AnimalMilkingPeriods.milking_period).order_by(
                AnimalMilkingPeriods.milking_period.desc()).all()
            # Assign milking period equal to first item of query above that is in descending order
            milking_period = q[0].milking_period
        # el if there are births calculate days from last birth and then assign correct milking period
        elif get_births:
            num_of_active_milking_periods = 0
            if get_births[0].end_of_milking_period == None:
                add_milking_period = False
                my_message = 'Δεν έχει κλείσει η προηγούμενη γαλακτική περίοδος. Δεν ανανεώθηκε ο πίνακας  με τις γαλακτικές περιόδους.'

            # Check if more than one milking periods have not closed
            for item in get_births:
                if item.end_of_milking_period == None:
                    num_of_active_milking_periods += 1
            if num_of_active_milking_periods > 1:
                add_milking_period = False
                my_message = 'Εχετε πολλαπλές ανοιχτές γαλακτικές περιόδους. Διορθώστε το. Δεν έγινε εισαγωγή γέννας στον πίνακα Γαλακτικών περιόδων.'
            # Check if last milking period is closed and if there are not any other open milking periods
            if get_births[0].end_of_milking_period != None and num_of_active_milking_periods == 0:
                my_message = 'Επιτυχής εισαγωγή εγγραφής στον πίνακα γαλακτικών περιόδων'
                add_milking_period = True
                milking_period = get_births[0].milking_period + 1

        # Check if animal has children
        if child_id != None:
            link_birth = AnimalBirth(parent_id=parent.id,
                                     child_id=child_id.id
                                     )
            if add_milking_period:
                milking_period = AnimalMilkingPeriods(
                    animal_id=parent.id,
                    milking_period=milking_period,
                    start_of_milking_period=child_id.date_of_birth
                )
            try:
                # add animal birth to the database
                db.session.add(link_birth)  # Add birth into AnimalBirths table
                db.session.flush()  # this will actually insert the record in the database and set link_birth.id automatically. The session, however, is not committed yet!
                # Add record into AnimalMilkingPeriods table
                db.session.add(milking_period)
                db.session.flush()
                db.session.commit()

                flash('Επιτυχής εισαγωγή νέας γέννας. ' +
                      my_message, category='success')
            except:
                # in case birth already exists
                flash('Error: Η γέννα έχει ήδη καταγραφεί.', category='error')
        else:
            # Receive message that child has not been recorded.
            flash('Error: Το ενώτιο του ζώου δεν έχει καταγραφεί στη βάση.')

        # redirect to animals page
        return redirect(url_for('admin.list_animals'))

    # load βιρτη template
    return render_template('home/birth.html', action="Add",
                           link_birth=link_birth, form=form,
                           parent=parent,
                           title="Link Birth")


@ admin.route('/script_to_delete', methods=['GET', 'POST'])
@ login_required
def script_to_delete():
    q = db.session.query(
        Milking.milking_period,
        func.sum(Milking.amount).label('recorded_amount'),
        func.sum(Milking.total_milk_up_to_today).label('estimated_amount'),
        func.max(Milking.days_from_last_birth).label('milked_days')) \
        .filter(Milking.animal_id == 1) \
        .group_by(Milking.milking_period) \
        .order_by(Milking.milking_period.asc()) \
        .all()
    x = [item for item in q]
    stats = dict(periods=[], recorded_amounts=[],
                 estimated_amount=[], milked_days=[])
    for i in range(len(q)):
        stats['periods'].append(q[i][0])
        stats['recorded_amounts'].append(q[i][1])
        stats['estimated_amount'].append(q[i][2])
        stats['milked_days'].append(q[i][3])

    return '<h1>'+str(stats)+'</h1>'


@ admin.route('/births/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_birth(id):
    """
    Delete a birth from the database
    """
    check_admin()
    birth = AnimalBirth.query.get_or_404(id)
    parent_id = birth.parent.id

    q_for_milking_periods = AnimalMilkingPeriods.query \
        .filter(AnimalMilkingPeriods.animal_id == parent_id) \
        .filter(AnimalMilkingPeriods.start_of_milking_period == birth.child.date_of_birth) \
        .all()

    q_for_milkings = Milking.query \
        .filter(Milking.animal_id == parent_id) \
        .filter(Milking.milking_period == q_for_milking_periods[0].milking_period) \
        .all()

    if q_for_milkings:
        delete_birth_of_animal = False
        flash('Υπάρχουν γαλακτομετρήσεις συνδεδεμένες με αυτή τη γέννα και δεν είναι δυνατή η διαγραφή της. Για να γίνει διαγραφή της γέννας πρέπει πρώτα να διαγράψετε τις γαλακτομετρήσεις που συνδέονται με αυτή τη γέννα', category='danger')
        # redirect to the alerts page
        return redirect(url_for('admin.animal_card', id=parent_id))

    if q_for_milking_periods and not q_for_milkings:
        delete_birth_of_animal = True
        deleted_milking_period = AnimalMilkingPeriods.query.get_or_404(
            q_for_milking_periods[0].id)
        my_message = 'Η γαλακτική περίοδος του ζώου διαγράφηκε.'

    if delete_birth_of_animal:
        db.session.delete(birth)
        db.session.flush()
        db.session.delete(deleted_milking_period)
        db.session.flush()
        db.session.commit()

        flash('Επιτυχής διαγραφή γέννας.'+my_message, category='success')

        # redirect to the alerts page
        return redirect(url_for('admin.animal_card', id=parent_id))

    return render_template(title="Delete Birth")

##### Function that update chart data on the animal card page ######


@ admin.route('/updateChart', methods=['GET', 'POST'])
@ login_required
def update_chart():
    """
    Send data to graph
    """
    check_admin()
    if request.method == 'POST':
        animal_id = request.form.get('animal_id')
        selected_year = request.form.get('selected_year')
        if selected_year:
            # updated_result = Milking.query.filter(
            #     Milking.milking_period == selected_year).filter(Milking.animal_id == animal_id).all()
            # updated_result = [item.amount for item in updated_result]
            # print('------------', updated_result)
            updated_result = getMilkingData(
                animal_id=animal_id, selected_year=selected_year)
            new_updated_result = dict(
                dates=[item[0].strftime("%Y/%m/%d")
                       for item in updated_result],
                amounts=[item[1] for item in updated_result],
                stable_amounts=[item[6] for item in updated_result])
            print('---------------', new_updated_result)
        else:
            new_updated_result = getMilkingData(
                animal_id=animal_id, selected_year=date.today().year)

    return jsonify(new_updated_result)


###########################################################################
###########################################################################
###################  Shipments Data  ######################################
###########################################################################
###########################################################################


@ admin.route('/shipments/', methods=['GET', 'POST'])
@ login_required
def list_shipments():
    """
    List all shipments
    """
    check_admin()
    shipments = Shipment.query.all()

    return render_template('home/shipments.html',
                           shipments=shipments, title="Shipments")


@ admin.route('/shipments/add', methods=['GET', 'POST'])
@ login_required
def add_shipment():
    """
    Add a shipment record to the database
    """
    check_admin()

    add_shipment = True
    form = ShipmentForm()
    if form.validate_on_submit():
        shipment = Shipment(amount=form.amount.data,
                            date_recorded=form.date_recorded.data
                            )
        try:
            # add shipment to the database
            db.session.add(shipment)
            db.session.commit()
            flash('You have successfully added a new shipment.')
        except:
            # in case shipment already exists
            flash('Error: Shipment data for this date already exists.')

        # redirect to shipments page
        return redirect(url_for('admin.list_shipments'))

    # load shipment template
    return render_template('home/shipment.html', action="Add",
                           add_shipment=add_shipment, form=form,
                           title="Add Shipment")


@ admin.route('/shipments/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_shipment(id):
    """
    Edit a Shipment
    """
    check_admin()

    add_shipment = False

    shipment = Shipment.query.get_or_404(id)
    form = ShipmentForm(obj=shipment)
    if form.validate_on_submit():
        shipment.amount = form.amount.data
        shipment.date_recorded = form.date_recorded.data
        db.session.commit()
        flash('You have successfully edited the shipment.')

        # redirect to the shipment page
        return redirect(url_for('admin.list_shipments'))

    form.amount.data = shipment.amount
    form.date_recorded.data = shipment.date_recorded
    return render_template('home/shipment.html', action="Edit",
                           add_shipment=add_shipment, form=form,
                           title="Edit Shipment")


@ admin.route('/shipments/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_shipment(id):
    """
    Delete a shipment from the database
    """
    check_admin()

    shipment = Shipment.query.get_or_404(id)
    db.session.delete(shipment)
    db.session.commit()
    flash('You have successfully deleted the shipment.')

    # redirect to the shipments page
    return redirect(url_for('admin.list_shipments'))

    return render_template(title="Delete Shipment")

###########################################################################
###########################################################################
###################  Income Data  #########################################
###########################################################################
###########################################################################


@ admin.route('/incomes/', methods=['GET', 'POST'])
@ login_required
def list_incomes():
    """
    List all income data
    """
    check_admin()
    incomes = Income.query.all()

    return render_template('home/incomes.html',
                           incomes=incomes, title="Income Data")


@ admin.route('/incomes/add', methods=['GET', 'POST'])
@ login_required
def add_income():
    """
    Add an income record to the database
    """
    check_admin()

    add_income = True
    income_category = IncomeCategory.query.all()
    form = IncomeForm()
    if form.validate_on_submit():
        income = Income(amount=form.amount.data,
                        date_recorded=form.date_recorded.data,
                        category_id=form.data['category'].id
                        )
        try:
            # add income to the database
            db.session.add(income)
            db.session.commit()
            flash('You have successfully added a new income record.')
        except:
            # in case income already exists
            flash('Error: Income data already exists.')

        # redirect to incomes page
        return redirect(url_for('admin.list_incomes'))

    # load shipment template
    return render_template('home/income.html', action="Add",
                           add_income=add_income, form=form,
                           income_category=income_category,
                           title="Add Income")


@ admin.route('/incomes/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_income(id):
    """
    Edit an Income Record
    """
    check_admin()

    add_income = False

    income = Income.query.get_or_404(id)
    form = IncomeForm(obj=income)
    if form.validate_on_submit():

        income.amount = form.amount.data
        income.date_recorded = form.date_recorded.data
        income.category_id = form.category.data.id
        db.session.commit()
        flash('You have successfully edited the income record.')

        # redirect to the income page
        return redirect(url_for('admin.list_incomes'))

    form.amount.data = income.amount
    form.date_recorded.data = income.date_recorded
    form.category.data = income.category_id
    return render_template('home/income.html', action="Edit",
                           add_income=add_income, form=form,
                           title="Edit Income")


@ admin.route('/incomes/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_income(id):
    """
    Delete an income record from the database
    """
    check_admin()

    income = Income.query.get_or_404(id)
    db.session.delete(income)
    db.session.commit()
    flash('You have successfully deleted the income record.')

    # redirect to the incomes page
    return redirect(url_for('admin.list_incomes'))

    return render_template(title="Delete Income")

###########################################################################
###########################################################################
###################  Income Category Data  ################################
###########################################################################
###########################################################################


@ admin.route('/income_categories', methods=['GET', 'POST'])
@ login_required
def list_income_categories():
    """
    List all income categories
    """
    check_admin()

    income_categories = IncomeCategory.query.all()

    return render_template('home/income_categories.html',
                           income_categories=income_categories, title="Income Categories")


@ admin.route('/income_categories/add', methods=['GET', 'POST'])
@ login_required
def add_income_category():
    """
    Add an income category record to the database
    """
    check_admin()

    add_income_category = True
    form = IncomeCategoryForm()
    if form.validate_on_submit():
        income_category = IncomeCategory(name=form.name.data
                                         )
        try:
            # add income category to the database
            db.session.add(income_category)
            db.session.commit()
            flash('You have successfully added a new income category.')
        except:
            # in case income category name already exists
            flash('Error: Income category name already exists.')

        # redirect to incomes page
        return redirect(url_for('admin.list_incomes'))

    # load department template
    return render_template('home/income_category.html', action="Add",
                           add_income_category=add_income_category, form=form,
                           title="Add Income Category")


@ admin.route('/income_categories/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_income_category(id):
    """
    Edit an Income Category
    """
    check_admin()

    add_income_category = False

    income_category = IncomeCategory.query.get_or_404(id)
    form = IncomeCategoryForm(obj=income_category)
    if form.validate_on_submit():
        income_category.name = form.name.data
        db.session.commit()
        flash('You have successfully edited the income category.')

        # redirect to the income categories page
        return redirect(url_for('admin.list_income_categories'))

    form.name.data = income_category.name
    return render_template('home/income_category.html', action="Edit",
                           add_income_category=add_income_category, form=form,
                           title="Edit Income Category")


@ admin.route('/income_categories/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_income_category(id):
    """
    Delete an income category from the database
    """
    check_admin()

    income_category = IncomeCategory.query.get_or_404(id)
    db.session.delete(income_category)
    db.session.commit()
    flash('You have successfully deleted the income category.')

    # redirect to the alerts page
    return redirect(url_for('admin.list_income_categories'))

    return render_template(title="Delete Income Category")

###########################################################################
###########################################################################
###################  Expenditure Data  ####################################
###########################################################################
###########################################################################


@ admin.route('/expenses/', methods=['GET', 'POST'])
@ login_required
def list_expenses():
    """
    List all expenses data
    """
    check_admin()
    expenses = Expense.query.all()

    return render_template('home/expenses.html',
                           expenses=expenses, title="Income Data")


@ admin.route('/expenses/add', methods=['GET', 'POST'])
@ login_required
def add_expense():
    """
    Add an expense record to the database
    """
    check_admin()

    add_expense = True
    expense_category = ExpenseCategory.query.all()
    form = ExpenseForm()
    if form.validate_on_submit():
        expense = Expense(amount=form.amount.data,
                          date_recorded=form.date_recorded.data,
                          category_id=form.data['category'].id
                          )
        try:
            # add expense to the database
            db.session.add(expense)
            db.session.commit()
            flash('Επιτυχής εγγραφή νέου εξόδου.')
        except:
            # in case expense already exists
            flash('Error: Τα δεδομένα εξόδου υπάρχουν ήδη στη βάση.')

        # redirect to expenses page
        return redirect(url_for('admin.list_expenses'))

    # load shipment template
    return render_template('home/expense.html', action="Add",
                           add_expense=add_expense, form=form,
                           expense_category=expense_category,
                           title="Add Expense")


@ admin.route('/expenses/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_expense(id):
    """
    Edit an Expense Record
    """
    check_admin()

    add_expense = False

    expense = Expense.query.get_or_404(id)
    form = ExpenseForm(obj=expense)
    if form.validate_on_submit():

        expense.amount = form.amount.data
        expense.date_recorded = form.date_recorded.data
        expense.category_id = form.category.data.id
        db.session.commit()
        flash('Επιτυχής τροποποίηση δεδομένων εξόδου.')

        # redirect to the expense page
        return redirect(url_for('admin.list_expenses'))

    form.amount.data = expense.amount
    form.date_recorded.data = expense.date_recorded
    form.category.data = expense.category_id
    return render_template('home/expense.html', action="Edit",
                           add_expense=add_expense, form=form,
                           title="Edit Expense")


@ admin.route('/expenses/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_expense(id):
    """
    Delete an expense record from the database
    """
    check_admin()

    expense = Expense.query.get_or_404(id)
    db.session.delete(expense)
    db.session.commit()
    flash('Επιτυχής διαγραφή δεδομένων εξόδου.')

    # redirect to the expenses page
    return redirect(url_for('admin.list_expenses'))

    return render_template(title="Delete Expense")

###########################################################################
###########################################################################
###################  Expense Category Data  ###############################
###########################################################################
###########################################################################


@ admin.route('/expense_categories', methods=['GET', 'POST'])
@ login_required
def list_expense_categories():
    """
    List all expenses categories
    """
    check_admin()

    expense_categories = ExpenseCategory.query.all()

    return render_template('home/expense_categories.html',
                           expense_categories=expense_categories, title="Expense Categories")


@ admin.route('/expense_categories/add', methods=['GET', 'POST'])
@ login_required
def add_expense_category():
    """
    Add an expense category record to the database
    """
    check_admin()

    add_expense_category = True
    form = ExpenseCategoryForm()
    if form.validate_on_submit():
        expense_category = ExpenseCategory(name=form.name.data
                                           )
        try:
            # add expense category to the database
            db.session.add(expense_category)
            db.session.commit()
            flash('Επιτυχής εισαγωγή νέας κατηγορίας εξόδου.')
        except:
            # in case expense category name already exists
            flash('Error: Η κατηγορία εξόδου υπάρχει ήδη.')

        # redirect to expenses page
        return redirect(url_for('admin.list_expenses'))

    # load department template
    return render_template('home/expense_category.html', action="Add",
                           add_expense_category=add_expense_category, form=form,
                           title="Add Expense Category")


@ admin.route('/expense_categories/edit/<int:id>', methods=['GET', 'POST'])
@ login_required
def edit_expense_category(id):
    """
    Edit an Expense Category
    """
    check_admin()

    add_expense_category = False

    expense_category = ExpenseCategory.query.get_or_404(id)
    form = ExpenseCategoryForm(obj=expense_category)
    if form.validate_on_submit():
        expense_category.name = form.name.data
        db.session.commit()
        flash('Επιτυχής τροποποίηση κατηγοορίας εξόδου.')

        # redirect to the expense categories page
        return redirect(url_for('admin.list_expense_categories'))

    form.name.data = expense_category.name
    return render_template('home/expense_category.html', action="Edit",
                           add_expense_category=add_expense_category, form=form,
                           title="Edit Expense Category")


@ admin.route('/expense_categories/delete/<int:id>', methods=['GET', 'POST'])
@ login_required
def delete_expense_category(id):
    """
    Delete an expense category from the database
    """
    check_admin()

    expense_category = ExpenseCategory.query.get_or_404(id)
    db.session.delete(expense_category)
    db.session.commit()
    flash('Επιτυχής διαγραφή κατηγορίας εξόδου.')

    # redirect to the expense categories page
    return redirect(url_for('admin.list_expense_categories'))

    return render_template(title="Delete Expense Category")


###########################################################################
###########################################################################
###################  Total Statistics  ####################################
###########################################################################
###########################################################################


@ admin.route('/total_statistics', methods=['GET', 'POST'])
@ login_required
def total_statistics():
    """
    Total Stats for all animals
    """
    check_admin()

    pass


# Absolute milking values ################

@ admin.route('/absolute_milking/<int:id>', methods=['GET', 'POST'])
@ login_required
def absolute_milking(id):
    """
    Absolute milking for all animals
    """
    check_admin()

    # Create an empty list in order for dict of results to get into.
    content = []
    final_amounts = []
    query = get_statistics_query(id)
    for item in query:
        stats = {

            "date_of_milking": item[3],
            "animal_sum": item[6],
            "animal_change": item[10],
            "milking_days": item[11]

        }
        content.append(stats)
    res = list(filter(lambda x: x["milking_days"] > 0, content))

    for i in range(len(res)):
        try:
            print(res[i]['date_of_milking'])

            date_diff = res[i+1]['milking_days'] - res[i]['milking_days']
            rate_of_change = res[i]['animal_change'] / date_diff
            daily_sum = res[i]['animal_sum']
            for j in range(int(date_diff)):

                if j > 0:
                    next_day = datetime.strptime(
                        res[i]['date_of_milking'], "%Y-%m-%d") + timedelta(days=j)
                    print(type(next_day))

                    animal_sum = daily_sum + (daily_sum*rate_of_change/100)
                    daily_sum = animal_sum

                    clues = {
                        "date": datetime.strftime(next_day, " %Y-%m-%d"),
                        "animal_sum": round(animal_sum, 2)
                    }
                    final_amounts.append(clues)

            # print(date_diff, '--- Animal Sum ---',
            #       res[i]['animal_sum'], '--- Change ---', res[i]['animal_change'], '--- rate ---', rate_of_change)

        except IndexError:
            pass

    print(sum(item['animal_sum'] for item in final_amounts))
    return '<h1>'+str(sum(item['animal_sum'] for item in final_amounts))+'</h1>'

#####################################################
#####################################################
############### Stable Section ######################
#####################################################
#####################################################


@ admin.route('/stable', methods=['GET', 'POST'])
def stable():
    available_milking_periods = Milking.query.distinct(
            Milking.milking_period).all()
    
    return render_template('home/test_table2.html',
                           available_milking_periods=[item.milking_period for item in available_milking_periods],
                           title="Stable Data")


@admin.route("/stable_all_animals/", methods=["POST", "GET"])
def stable_all_animals():

    available_milking_periods = Milking.query.distinct(
            Milking.milking_period).all()
    get_period = 1
    if request.method == 'POST':
        sent_data = request.get_json(force = True)
        get_period = sent_data['selected_period']
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            '''
                select  animal_milking_periods.start_of_milking_period as start_date,
                        animal_milking_periods.end_of_milking_period as end_date,
                        count(a.animal_id) as number_of_recorded_milkings,a.animal_id,
                        a.ear_tag,
						animals.animal_box,
                        animals.status,
                        ROUND(SUM(total_milk_up_to_today)/1000::NUMERIC,2) as total_milk,
                        max(a.days_from_last_birth) as days_milked,
                        ROUND(SUM(total_milk_up_to_today) / NULLIF(max(a.days_from_last_birth),0)/1000::NUMERIC,2) as average_milk,
                        ROUND(((SUM(total_milk_up_to_today) / a.total_sum)*100)::NUMERIC,3) as check
                from(
                    select *,(select CAST(sum(total_milk_up_to_today) AS FLOAT) 
                            from milkings WHERE milking_period=1) as total_sum
                    from milkings
                    WHERE milking_period=%s

                )  as a
                join animal_milking_periods on animal_milking_periods.animal_id = a.animal_id
                join animals on animals.id = a.animal_id
                group by a.animal_id, a.ear_tag, a.total_sum, animal_milking_periods.start_of_milking_period, 
				animal_milking_periods.end_of_milking_period, animals.status, animals.animal_box
                order by average_milk desc

                        ''', (str(get_period))
        )
        milking_list = cursor.fetchall()
        data = []
        for row in milking_list:
            if row['average_milk'] == None:
                row['average_milk'] = 0
            if row['end_date'] != None:
                row['end_date'] = row['end_date'].strftime("%d/%m/%Y")
            data.append({
                        'ear_tag': row['ear_tag'],
                        'animal_id': row['animal_id'],
                        'total_milk': row['total_milk'],
                        'days_milked': row['days_milked'],
                        'average_milk': row['average_milk'],
                        'start_date': row['start_date'].strftime("%d/%m/%Y"),
                        'end_date': row['end_date'],
                        'animal_box':row['animal_box'],
                        'status': row['status']
                        })
        
   
        response = {
                'data':data,
                'available_milking_periods':[item.milking_period for item in available_milking_periods]
            }
        return jsonify(response)
    
@ admin.route('/stable/custom_data', methods=['GET', 'POST'])
def stable_return_custom_data():
    available_milking_periods = Milking.query.distinct(
            Milking.milking_period).all()
    
    return render_template('home/test_table_custom_data.html',
                           available_milking_periods=[item.milking_period for item in available_milking_periods],
                           title="Stable Data")

@admin.route("/stable_custom_data/", methods=["POST", "GET"])
def stable_custom_data():

    available_milking_periods = Milking.query.distinct(
            Milking.milking_period).all()
    get_period = 1
    if request.method == 'POST':
        sent_data = request.get_json(force = True)
        get_period = sent_data['selected_period']
        downloadRequest = sent_data['download']
        print('!!!!!!!!!!!!!!!!!!!!!',downloadRequest)
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            '''
               with total_stats as (
                    SELECT milkings.animal_id, milkings.ear_tag, days_from_last_birth,
                    sum(amount) as total_amount,
                    date(date_recorded) as milking_date,
                    sum(total_milk_up_to_today) as total_milk
                    from milkings
                    where milkings.milking_period = %s
                    group by milkings.animal_id,milkings.ear_tag, days_from_last_birth, date(date_recorded)
                    ORDER BY animal_id asc, date(date_recorded) desc
                    ) 
                    SELECT 
                        total_stats.animal_id, total_stats.ear_tag,
                        animal_milking_periods.start_of_milking_period,
                        animals.animal_box,
                        days_from_last_birth,milking_date,
                        total_amount,
                        sum(total_milk) over (PARTITION BY total_stats.animal_id ORDER BY milking_date),
                        animals.status
                    FROM total_stats 
                    join animal_milking_periods on animal_milking_periods.animal_id = total_stats.animal_id
                    join animals on animals.id = total_stats.animal_id
                    where animal_milking_periods.milking_period=%s
                    GROUP BY total_stats.animal_id,total_stats.ear_tag,total_stats.days_from_last_birth,
                            total_stats.milking_date,total_stats.total_amount,
                            total_stats.total_milk,animal_milking_periods.start_of_milking_period,
                            animals.animal_box, animals.status
                    order by animal_id asc, milking_date desc

            ''', [str(get_period),str(get_period)]
        )
        milking_list = cursor.fetchall()

        checked_animals = []
        counter = -1
        animal_counter = 0
        longest_value = 0
        animal_dict_list = []

        for row in milking_list:

            if row[0] not in checked_animals:
                animal_counter = 0 
                checked_animals.append(row[0])
                if row[4] == 0:
                    row[4] = row[6]
                animal = {'id':row[0],
                          'ear_tag':row[1],
                          'start_of_milking_period':row[2].strftime("%d/%m/%Y"),
                          'animal_box':row[3],
                          'status':row[8],
                          str(animal_counter):{
                          'sum':round(float(row[7]/1000),2),
                          'days':row[4],
                          'avg':round((float(row[7])/float(row[4]))/1000,2)
                          }
                          }           
                animal_dict_list.append(animal)
                counter +=1
            elif row[0] in checked_animals:
                animal_counter +=1
                if animal_counter > longest_value:
                    longest_value = animal_counter
                if row[4] == 0:
                    row[4] = row[6]
                animal_dict_list[counter].update(
                        {str(animal_counter): {
                            'sum':round(float(row[7]/1000),2),
                            'days':row[4],
                            'avg':round((float(row[7])/float(row[4]))/1000,2)
                            }
                        }
                        )
                
        # columns=['id','ear_tag','start_of_milking_period']
        if downloadRequest:

            df = pd.json_normalize(animal_dict_list, max_level=1)

            df.to_excel('dict1.xlsx')
            split_values = df['animal_box'].unique()
            with pd.ExcelWriter("dict1.xlsx") as writer:
                for value in split_values:
                    if str(value) =='nan':
                        df1 = df[df['animal_box'].isnull()]
                        df1.to_excel(writer, sheet_name='Άγνωστο Box', index=False)
                    else:
                        df1 = df[df['animal_box'] == value]
                        print(df1)
                        df1.to_excel(writer, sheet_name='Box_'+str(int(value)), index=False)
            downloadFile()
            

   
        response = {
                'data':animal_dict_list,
                'available_milking_periods':[item.milking_period for item in available_milking_periods],
                'longest': longest_value,
                
            }
        
        return jsonify(response)

@admin.route('/download')
def downloadFile ():
    #For windows you need to use drive name [ex: F:/Example.pdf]
    path = "..\dict1.xlsx"
    return send_file(path, as_attachment=True)


@admin.route("/stable_calendar/", methods=["POST", "GET"])
def stable_calendar():

    query_available_milking_years = db.session.query(extract('year', MilkingPerDay.date_recorded).label('year'))\
        .distinct().order_by(asc('year'))
    available_milking_years = [int(item['year'])
                               for item in query_available_milking_years]

    get_year = available_milking_years[0]

    if request.method == 'POST':
        get_year = request.form.get('yearSelect')

    basic_query = MilkingPerDay.query.filter(
        extract('year', MilkingPerDay.date_recorded) == int(get_year)).order_by(MilkingPerDay.date_recorded.asc()).all()

    available_years = [item for item in basic_query]

    return render_template('home/stable_calendar.html',
                           available_years=available_years,
                           available_milking_years=available_milking_years,
                           title="Ζώα Στάβλου")


#####################################################
#####################################################
####### Functions to perform specific Tasks #########
#####################################################
#####################################################


def auto_link_birth(get_parent_id, get_child_id):
    """
    Add a relationship to Animal-Births table
    """
    # Get parent
    parent = Animal.query.get_or_404(get_parent_id)
    child_id = Animal.query.filter_by(id=get_child_id).first()
    newBirth = AnimalBirth(
        parent_id=get_parent_id,
        child_id=get_child_id)

    db.session.add(newBirth)
    db.session.commit()
    has_child_insert_milking_period_table(get_parent_id, get_child_id)

    return


@admin.route('/check_milking', methods=['POST'])
def check_milking():
    animal_id = int(float(0))
    # Get ear_tag from form
    ear_tag = request.form['send']
    # Check if ear_tag is on database
    check = Animal.query \
        .filter_by(ear_tag=ear_tag) \
        .filter_by(status=True) \
        .first()
    # If ear_tag is valid check whether the animal has children
    # Do so because milking days from last birth is recorded on the database
    if check:
        q = db.session.query(AnimalMilkingPeriods).\
            filter(AnimalMilkingPeriods.animal_id == check.id, AnimalMilkingPeriods.end_of_milking_period == None).\
            all()
        if q:
            children = True
            num_of_children = len(q)
            animal_id = check.id

        else:
            children = False
            num_of_children = 0
            animal_id = check.id
    else:
        children = False  # In case animal ear tag is invalid return children False
        num_of_children = 0

    if check:
        exists = True
    else:
        exists = False

    return jsonify(exists=exists, children=children, num_of_children=num_of_children, animal_id=int(float(animal_id)))


def has_child_insert_milking_period_table(parent_id, child_id):
    # Check child details
    child = Animal.query.filter_by(id=child_id).first()
    # Check if parent has given any birth
    has_been_milked_again = AnimalMilkingPeriods.query.filter_by(
        animal_id=parent_id).all()
    # If it is first birth
    if not has_been_milked_again:
        # Query to get last milking period that is active
        q = AnimalMilkingPeriods.query.distinct(AnimalMilkingPeriods.milking_period).order_by(
            AnimalMilkingPeriods.milking_period.desc()).all()
        # Assign milking period equal to first item of query above that is in descending order
        milking_period = q[0].milking_period
        first_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                             milking_period=milking_period,
                                             start_of_milking_period=child.date_of_birth)
        db.session.add(first_milking)
        db.session.commit()
    else:
        # If it is not first birth get a list of all birth dates
        query_for_births = db.session.query(AnimalMilkingPeriods).\
            filter(AnimalMilkingPeriods.animal_id == parent_id).\
            order_by(AnimalMilkingPeriods.start_of_milking_period.asc()).\
            all()

        if (child.date_of_birth - query_for_births[-1].start_of_milking_period).days > 60:
            milking_period = query_for_births[-1].milking_period
            next_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                                milking_period=milking_period+1,
                                                start_of_milking_period=child.date_of_birth)
            db.session.add(next_milking)
            db.session.commit()

    return


@ admin.route('/not_have_child_insert_milking_period_table/<int:parent_id>', methods=['GET', 'POST'])
@ login_required
def get_form_of_new_milking(parent_id):
    if request.method == "POST":
        data = request.form.to_dict()

        parent = Animal.query.filter_by(id=parent_id).first()
        start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()

        # Check if parent has given any birth
        has_been_milked_again = AnimalMilkingPeriods.query.filter_by(
            animal_id=parent_id).all()
        # If it is first birth
        if not has_been_milked_again and start_date <= date.today():
            # Query to get last milking period that is active
            q = AnimalMilkingPeriods.query.distinct(AnimalMilkingPeriods.milking_period).order_by(
                AnimalMilkingPeriods.milking_period.desc()).all()
            # Assign milking period equal to first item of query above that is in descending order
            milking_period = q[0].milking_period

            first_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                                 milking_period=milking_period,
                                                 start_of_milking_period=start_date.strftime(
                                                     "%Y/%m/%d"),
                                                 has_child=False)
            try:
                db.session.add(first_milking)
                db.session.commit()
                flash('Επιτυχής εισαγωγή γέννας.', category='success')

            except:
                flash('Κάτι πήγε στραβά.', category='danger')

            return redirect(url_for('admin.animal_card', id=parent_id))

        elif has_child_insert_milking_period_table and start_date <= date.today():
            # If it is not first birth get a list of all birth dates
            query_for_births = db.session.query(AnimalMilkingPeriods).\
                filter(AnimalMilkingPeriods.animal_id == parent_id).\
                order_by(AnimalMilkingPeriods.start_of_milking_period.asc()).\
                all()
            # Not allowed to have two active milking periods
            if query_for_births[-1].end_of_milking_period == None:
                flash('Υπάρχει ενεργή γαλακτική περίοδος. Πρώτα τερματίστε την ενεργή γαλακτική περίοδο και μετά εισάγετε νέα γέννα', category='danger')
                return redirect(url_for('admin.animal_card', id=parent_id))

            if (start_date - query_for_births[-1].start_of_milking_period).days > 60:
                milking_period = query_for_births[-1].milking_period
                next_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                                    milking_period=milking_period+1,
                                                    start_of_milking_period=start_date.strftime(
                                                        "%Y/%m/%d"),
                                                    has_child=False)
            try:
                db.session.add(next_milking)
                db.session.commit()
                flash('Επιτυχής εισαγωγή γέννας.', category='success')
            except:
                flash('Δεν καταγράφηκε η γεννα επειδή δεν άλλαξε η γαλακτική περίοδος λόγω ημερών απο την προηγούμενη γέννα.', category='danger')

            return redirect(url_for('admin.animal_card', id=parent_id))

        else:
            # redirect to animal card.
            flash('Δεν καταγράφηκε η γεννα επειδή η ημερομηνία γέννησης είναι μεγαλύτερη απο τη σημερινή.', category='danger')
            return redirect(url_for('admin.animal_card', id=parent_id))

    return redirect(url_for('admin.animal_card', id=parent_id))


@ admin.route('/stop_current_milking_period/<int:parent_id>', methods=['GET', 'POST'])
@ login_required
def stop_milking_period(parent_id):
    if request.method == "POST":
        data = request.form.to_dict()

        parent = Animal.query.filter_by(id=parent_id).first()
        stop_date = datetime.strptime(data['stop_date'], "%Y-%m-%d").date()

        # Check if parent has given any birth
        has_been_milked_again = AnimalMilkingPeriods.query.filter_by(
            animal_id=parent_id).all()
        # If it is first birth
        if not has_been_milked_again:
            flash('Δεν έχει καταγραφεί γέννα του ζώου στη βάση.', category='danger')

            return redirect(url_for('admin.animal_card', id=parent_id))

        elif has_child_insert_milking_period_table and stop_date <= date.today():

            # If it is not first birth get the selected milking period
            query_for_milking_periods = db.session.query(AnimalMilkingPeriods).\
                filter(AnimalMilkingPeriods.animal_id == parent_id, AnimalMilkingPeriods.id == int(data['select_milking_period_id'])).\
                first()
            # Set end_date equals to given stop date
            query_for_milking_periods.end_of_milking_period = stop_date
            db.session.commit()
            flash('Επιτυχής εισαγωγή τέλους γαλακτομέτρησης.', 'success')
            # Redirect to animal_card page
            return redirect(url_for('admin.animal_card', id=parent_id))

        else:
            # redirect to animal card.
            flash('Δεν καταγράφηκε η ημερομηνια τελευταίας γαλακτομέτρης επειδή είναι μεγαλύτερη απο τη σημερινή.', category='danger')
            return redirect(url_for('admin.animal_card', id=parent_id))

    return redirect(url_for('admin.animal_card', id=parent_id))

@ admin.route('/add_animal_box/<int:animal_id>', methods=['GET', 'POST'])
@ login_required
def add_animal_box(animal_id):
    if request.method == "POST":
        data = request.form.to_dict()
        q = Animal.query.filter_by(id=animal_id).first()


        if data['select_animal_box'] == 'None':
            q.animal_box = None
        else:
            q.animal_box = data['select_animal_box']
        db.session.commit()  

        flash('Επιτυχής εισαγωγή αριθμού Box που ανήκει το ζώο.', 'success')
    return redirect(url_for('admin.animal_card', id=animal_id))


@ admin.route('/silent_not_have_child_insert_milking_period_table/<int:parent_id>', methods=['GET', 'POST'])
@ login_required
def silent_get_form_of_new_milking(parent_id):
    if request.method == "POST":
        data = request.form.to_dict()
        parent = Animal.query.filter_by(id=parent_id).first()
        start_date = datetime.strptime(data['start_date'], "%Y-%m-%d").date()

        # Check if parent has given any birth
        has_been_milked_again = AnimalMilkingPeriods.query.filter_by(
            animal_id=parent_id).all()
        # If it is first birth
        if not has_been_milked_again and start_date <= date.today():
            # Query to get last milking period that is active
            q = AnimalMilkingPeriods.query.distinct(AnimalMilkingPeriods.milking_period).order_by(
                AnimalMilkingPeriods.milking_period.desc()).all()
            # Assign milking period equal to first item of query above that is in descending order
            milking_period = q[0].milking_period
            first_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                                 milking_period=milking_period,
                                                 start_of_milking_period=start_date.strftime(
                                                     "%Y/%m/%d"),
                                                 has_child=False)
            try:
                db.session.add(first_milking)
                db.session.commit()
                result = 'Επιτυχής εισαγωγή γέννας.'

            except:
                result = 'Κάτι πήγε στραβά.'

        elif has_child_insert_milking_period_table and start_date <= date.today():
            # If it is not first birth get a list of all birth dates
            query_for_births = db.session.query(AnimalMilkingPeriods).\
                filter(AnimalMilkingPeriods.animal_id == parent_id).\
                order_by(AnimalMilkingPeriods.start_of_milking_period.asc()).\
                all()

            if (start_date - query_for_births[-1].start_of_milking_period).days > 60:
                milking_period = query_for_births[-1].milking_period
                next_milking = AnimalMilkingPeriods(animal_id=parent_id,
                                                    milking_period=milking_period+1,
                                                    start_of_milking_period=start_date.strftime(
                                                        "%Y/%m/%d"),
                                                    has_child=False)
            try:
                db.session.add(next_milking)
                db.session.commit()
                result = 'Επιτυχής εισαγωγή γέννας.'
            except:
                result = 'Δεν καταγράφηκε η γεννα επειδή δεν άλλαξε η γαλακτική περίοδος λόγω ημερών απο την προηγούμενη γέννα.'

        else:
            # redirect to animal card.
            result = 'Δεν καταγράφηκε η γεννα επειδή η ημερομηνία γέννησης είναι μεγαλύτερη απο τη σημερινή.'
    return jsonify(result)


@ admin.route('/test_route', methods=['GET', 'POST'])
@ login_required
def test_route():
    q = Animal.query.filter_by(id=2001).first()

    # Get name of alerts for animal
    alerts = [item.alert_id_alert.name for item in q.alerts]
    # Get all data for all children as every item is animal instance
    children = [item.child for item in q.parent]
    # Get all data for all milkings as every item is milking instance
    milkings = [item for item in q.milkigs]

    animal_data = {'alerts': [item.alert_id_alert.name for item in q.alerts],
                   'children': [item.child for item in q.parent],
                   'milkings': [item for item in q.milkigs],
                   'milking_periods': [item for item in q.set_milking_period]}
    # Get current milking period
    # sorted([item.milking_period for item in animal_data['milking_periods']], reverse=True)[0]
    return '<h1>'+str([item.length_of_milking_period for item in animal_data['milking_periods']])+'</h1>'


#################################################################
#################################################################
################## Scripts to run on production #################
#################################################################
#################################################################

# 1. Script to add milking periods to animal_milking_periods table.


@ admin.route('/add_milking_periods_script', methods=['GET', 'POST'])
@ login_required
def add_milking_periods_script():
    q = AnimalBirth.query

    d = dict([(item.id, []) for item in q])
    for item in q:
        d[item.id].append(item.parent.date_of_birth)
        d[item.id].append(item.child.date_of_birth)
    for item in q:
        query = AnimalMilkingPeriods.query.filter(
            AnimalMilkingPeriods.animal_id == item.parent.id).first()

        if not query:

            first_milking = AnimalMilkingPeriods(animal_id=item.parent.id,
                                                 milking_period=1,
                                                 start_of_milking_period=item.child.date_of_birth.strftime(
                                                     "%Y/%m/%d")
                                                 )
            try:
                db.session.add(first_milking)
                db.session.commit()
                print('Επιτυχής εισαγωγή γέννας.')

            except:
                print('Κάτι πήγε στραβά.')

    return '<h1>'+str(d)+'</h1>'

# 2. Script to add time of milking on milkings table


@ admin.route('/add_milking_times_script', methods=['GET', 'POST'])
@ login_required
def add_milking_times_script():
    q = Milking.query

    for item in q:

        if item.date_recorded.hour >= 3 and item.date_recorded.hour <= 10:
            time_of_milking = 'MORNING'
        elif item.date_recorded.hour >= 11 and item.date_recorded.hour <= 17:
            time_of_milking = 'MIDDAY'
        else:
            time_of_milking = 'EVENING'
        try:
            item.milking_time = time_of_milking
            db.session.commit()
            print('Επιτυχής εισαγωγή ώρας.')

        except:
            print('Κάτι πήγε στραβά.')

    return '<h1>'+str('Hello')+'</h1>'

# 3. Script to add milking periods =1 on milkings table


@ admin.route('/add_milking_period_to_milking_table_script', methods=['GET', 'POST'])
@ login_required
def add_milking_period_to_milking_table_script():
    q = Milking.query

    for item in q:

        try:
            item.milking_period = 1
            db.session.commit()
            print('Επιτυχής εισαγωγή περιόδου.')

        except:
            print('Κάτι πήγε στραβά.')

    return '<h1>'+str('Hello')+'</h1>'

# 4. Script to add days from last birth on milkings table


@ admin.route('/add_days_from_last_birth_script', methods=['GET', 'POST'])
@ login_required
def add_days_from_last_birth_script():
    q = Milking.query

    # Step 1 check if all animals have children, otherwise show me which animal has no children
    # and then add new birth for each
    list_of_animals_have_no_children = []
    list_of_animals_have_no_parent = []
    foo = ['10%', '9%']  # Add params for like search

    ###############################################
    # First, run this. If returns empty list then proceed to step 2. Otherwise fix parents and children issues.
    ###############################################
    # # This query gives animals having no children
    # for item in q:
    #     animal = Animal.query.filter(Animal.id == item.animal_id).first()
    #     if len(animal.parent) == 0:
    #         list_of_animals_have_no_children.append(animal.id)

    # # This query gives animals having no parent
    # query = Animal.query \
    #     .filter(or_(*[cast(Animal.ear_tag, String()).like(name) for name in foo]))
    # for item in query:
    #     if not item.child:
    #         list_of_animals_have_no_parent.append(item.id)
    # return '<h1>'+str([item for item in list_of_animals_have_no_parent] + [item for item in list_of_animals_have_no_children])+'</h1>'

    ##########################################
    # Step 2 add milking times to database
    ##########################################

    # for item in q:
    #     animal = Animal.query.filter(Animal.id == item.animal_id).first()
    #     child_date_of_birth = animal.parent[0].child.date_of_birth
    #     milking_date = item.date_recorded.date()
    #     difference = (milking_date - child_date_of_birth).days

    #     try:
    #         item.days_from_last_birth = difference
    #         db.session.commit()
    #         print('Επιτυχής εισαγωγή διαφοράς μέρας.')

    #     except:
    #         print('Κάτι πήγε στραβά.')

    return '<h1>'+str('All recorded have been updated!!!!')+'</h1>'

# 5. Script to add percent of change based on time milking


@ admin.route('/add_change_from_last_milking_script', methods=['GET', 'POST'])
@ login_required
def add_change_from_last_milking_script():
    animals_have_been_milked = Milking.query.distinct(Milking.animal_id).all()
    for animal in animals_have_been_milked:
        # Get all milkings for each distinct animal
        milking_query_morning = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MORNING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        milking_query_midday = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MIDDAY') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        milking_query_evening = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'EVENING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        # Get all amounts from retrieved milkings
        amounts_morning = [item.amount for item in milking_query_morning]
        amounts_midday = [item.amount for item in milking_query_midday]
        amounts_evening = [item.amount for item in milking_query_evening]
    # Morning loop
        for i in range(0, len(amounts_morning)):
            if i == 0:
                milking_query_morning[i].change_from_last_milking = 0
                db.session.commit()
            else:
                milking_query_morning[i].change_from_last_milking = round(
                    (
                        (float(amounts_morning[i]) -
                         amounts_morning[i-1])/amounts_morning[i-1]
                    ), 3)
                db.session.commit()
        # Midday loop
        for i in range(0, len(amounts_midday)):
            if i == 0:
                milking_query_midday[i].change_from_last_milking = 0
                db.session.commit()
            else:
                milking_query_midday[i].change_from_last_milking = round(
                    (
                        (float(amounts_midday[i]) -
                         amounts_midday[i-1])/amounts_midday[i-1]
                    ), 3)
                db.session.commit()
        # Evening loop
        for i in range(0, len(amounts_evening)):
            if i == 0:
                milking_query_evening[i].change_from_last_milking = 0
                db.session.commit()
            else:
                milking_query_evening[i].change_from_last_milking = round(
                    (
                        (float(amounts_evening[i]) -
                         amounts_evening[i-1])/amounts_evening[i-1]
                    ), 3)
                db.session.commit()

    # counter = 0
    # for item in milking_query:
    #     if counter == 0:
    #         item.change_from_last_milking = 0
    #         db.session.commit()
    #         counter += 1
    #     else:

    #         change_from_last_milking = round(
    #                         (
    #                             (float(my_list[i+1]) -
    #                              amounts[-1])/amounts[-1]
    #                         ), 3)

    # print(milking_query[0])
    # per_day = {'amount': [1310, 1390, 1660, 1580],
    #            'rate': [0.061, 0.1942, -0.048],
    #            'diff': [10, 13, 17]}
    # morning = {'amount': [440, 670, 610, 520],
    #            'rate': [0.522, -0.089, -0.147],
    #            'diff': [10, 13, 17]}
    # midday = {'amount': [500, 440, 550, 580],
    #           'rate': [-0.12, 0.25, 0.054],
    #           'diff': [10, 13, 17]
    #           }
    # evening = {'amount': [370, 280, 500, 480],
    #            'rate': [-0.243, 0.785, -0.04],
    #            'diff': [10, 13, 17]

    #            }

    # total_per_day = 0
    # total_per_morning = 0
    # total_per_midday = 0
    # total_per_evening = 0
    # dict_variable = {key: value for (key, value) in per_day.items()}
    # for i in range(1, len(dict_variable['amount'])):

    #     total_per_day += calculate_total_milk(
    #         per_day['amount'][i-1], per_day['amount'][i], per_day['rate'][i-1], per_day['diff'][i-1])
    # print(total_per_day)
    # for i in range(1, len(morning['amount'])):
    #     total_per_morning += calculate_total_milk(
    #         morning['amount'][i-1], morning['amount'][i], morning['rate'][i-1], morning['diff'][i-1])
    # print(total_per_morning)
    # for i in range(1, len(midday['amount'])):
    #     total_per_midday += calculate_total_milk(
    #         midday['amount'][i-1], midday['amount'][i], midday['rate'][i-1], midday['diff'][i-1])
    # print(total_per_midday)
    # for i in range(1, len(evening['amount'])):
    #     total_per_evening += calculate_total_milk(
    #         evening['amount'][i-1], evening['amount'][i], evening['rate'][i-1], evening['diff'][i-1])
    # print(total_per_evening)
    # final_total = total_per_morning+total_per_midday+total_per_evening
    # print(final_total)
    return '<h1>'+str('All recorded have been updated!!!!')+'</h1>'

# 6. Script to add total milk up to date recorded based on time milking


@ admin.route('/add_total_milk_up_to_current_date_script', methods=['GET', 'POST'])
@ login_required
def add_total_milk_up_to_current_date_script():

    animals_have_been_milked = Milking.query.distinct(Milking.animal_id).all()

    for animal in animals_have_been_milked:
        # Get all milkings for each distinct animal
        milking_query_morning = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MORNING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        milking_query_midday = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MIDDAY') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        milking_query_evening = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'EVENING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()
        # Get all amounts from retrieved milkings

        morning = {'amount': [item.amount for item in milking_query_morning],
                   'rate': [item.change_from_last_milking for item in milking_query_morning],
                   'diff': [item.days_from_last_birth for item in milking_query_morning],
                   'date': [date.strftime(item.date_recorded, "%Y-%m-%d") for item in milking_query_morning]

                   }

        midday = {'amount': [item.amount for item in milking_query_midday],
                  'rate': [item.change_from_last_milking for item in milking_query_midday],
                  'diff': [item.days_from_last_birth for item in milking_query_midday],
                  'date': [date.strftime(item.date_recorded, "%Y-%m-%d") for item in milking_query_midday]

                  }

        evening = {'amount': [item.amount for item in milking_query_evening],
                   'rate': [item.change_from_last_milking for item in milking_query_evening],
                   'diff': [item.days_from_last_birth for item in milking_query_evening],
                   'date': [date.strftime(item.date_recorded, "%Y-%m-%d") for item in milking_query_midday]

                   }

        if milking_query_morning:
            for i in range(len(morning['amount'])):
                if i == 0:
                    if morning['diff'][i] != 0:
                        last_milking = morning['amount'][i] - \
                            (morning['amount'][i] * 0.2)
                        milking_query_morning[i].total_milk_up_to_today = calculate_total_milk(
                            last_milking, morning['amount'][i], 0.2, morning['diff'][i])
                        db.session.commit()
                    else:
                        milking_query_morning[i].total_milk_up_to_today = morning['amount'][i]
                        db.session.commit()

                else:
                    milking_query_morning[i].total_milk_up_to_today = calculate_total_milk(
                        morning['amount'][i-1], morning['amount'][i], morning['rate'][i], morning['diff'][i] - morning['diff'][i-1])
                    db.session.commit()

        if milking_query_midday:
            for i in range(len(midday['amount'])):
                if i == 0:
                    if midday['diff'][i] != 0:
                        last_milking = midday['amount'][i] - \
                            (midday['amount'][i] * 0.2)
                        milking_query_midday[i].total_milk_up_to_today = calculate_total_milk(
                            last_milking, midday['amount'][i], 0.2, midday['diff'][i])
                        db.session.commit()
                    else:
                        milking_query_midday[i].total_milk_up_to_today = midday['amount'][i]
                        db.session.commit()
                else:
                    milking_query_midday[i].total_milk_up_to_today = calculate_total_milk(
                        midday['amount'][i-1], midday['amount'][i], midday['rate'][i], midday['diff'][i] - midday['diff'][i-1])
                    db.session.commit()

        if milking_query_evening:

            for i in range(len(evening['amount'])):
                if i == 0:
                    if evening['diff'][i] != 0:
                        last_milking = evening['amount'][i] - \
                            (evening['amount'][i] * 0.2)
                        milking_query_evening[i].total_milk_up_to_today = calculate_total_milk(
                            last_milking, evening['amount'][i], 0.2, evening['diff'][i])
                        db.session.commit()
                    else:
                        milking_query_evening[i].total_milk_up_to_today = evening['amount'][i]
                        db.session.commit()

                else:
                    milking_query_evening[i].total_milk_up_to_today = calculate_total_milk(
                        evening['amount'][i-1], evening['amount'][i], evening['rate'][i], evening['diff'][i] - evening['diff'][i-1])
                    db.session.commit()

    return '<h1>'+str('All recorded have been updated!!!!')+'</h1>'

# 7. Optional script


@ admin.route('/add_milk_per_day_on_specif_table_script', methods=['GET', 'POST'])
@ login_required
def add_milk_per_day_on_specif_table_script():

    animals_have_been_milked = Milking.query.distinct(Milking.animal_id).all()

    for animal in animals_have_been_milked:
        milking_days = MilkingPerDay.query.distinct(
            MilkingPerDay.date_recorded).all()
        passed_days = [item.date_recorded for item in milking_days]

        # Get all milkings for each distinct animal
        milking_query_morning = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MORNING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()

        milking_query_midday = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'MIDDAY') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()

        milking_query_evening = Milking.query \
            .filter(Milking.animal_id == animal.animal_id) \
            .filter(Milking.milking_time == 'EVENING') \
            .order_by(Milking.id.asc(), cast(Milking.date_recorded, Date).asc()) \
            .all()

        # Get all amounts from retrieved milkings
        morning = {'amount': [item.amount for item in milking_query_morning],
                   'rate': [item.change_from_last_milking for item in milking_query_morning],
                   'diff': [item.days_from_last_birth for item in milking_query_morning],
                   'date': [item.date_recorded for item in milking_query_morning]

                   }

        midday = {'amount': [item.amount for item in milking_query_midday],
                  'rate': [item.change_from_last_milking for item in milking_query_midday],
                  'diff': [item.days_from_last_birth for item in milking_query_midday],
                  'date': [item.date_recorded for item in milking_query_midday]

                  }

        evening = {'amount': [item.amount for item in milking_query_evening],
                   'rate': [item.change_from_last_milking for item in milking_query_evening],
                   'diff': [item.days_from_last_birth for item in milking_query_evening],
                   'date': [item.date_recorded for item in milking_query_evening]

                   }

        if milking_query_morning:

            for i in range(len(morning['amount'])):
                if i == 0:  # Parse first milking of ewe
                    if morning['diff'][i] != 0:
                        last_milking = morning['amount'][i] - \
                            (morning['amount'][i] * 0.2)

                        per_day = calculate_total_milk_v2(last_milking, morning['amount'][i], 0.2, morning['diff'][i],
                                                          morning['date'][i] - timedelta(days=morning['diff'][i]), morning['date'][i])

                        for i in range(len(per_day['day_recorded'])):

                            if per_day['day_recorded'][i].date() not in passed_days:

                                entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                      amount=math.ceil(
                                                          (per_day['amount_recorded'][i])),
                                                      num_of_animals_milked=1)

                                db.session.add(entry)
                                db.session.commit()
                                passed_days.append(
                                    per_day['day_recorded'][i].date())
                            else:
                                updated_date = MilkingPerDay.query.filter_by(
                                    date_recorded=per_day['day_recorded'][i].date()).first()
                                updated_date.amount = updated_date.amount + \
                                    math.ceil(per_day['amount_recorded'][i])
                                updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                                db.session.commit()

                    else:

                        # Add amount and date to milk_per_day table
                        if morning['date'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=morning['date'][i].date(),
                                                  amount=morning['amount'][i],
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(morning['date'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=morning['date'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                morning['amount'][i]
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()

                else:

                    per_day = calculate_total_milk_v2(morning['amount'][i-1], morning['amount'][i], morning['rate'][i], morning['diff'][i] - morning['diff'][i-1],
                                                      morning['date'][i-1], morning['date'][i])

                    for i in range(len(per_day['day_recorded'])):

                        if per_day['day_recorded'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                  amount=math.ceil(
                                                      per_day['amount_recorded'][i]),
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(
                                per_day['day_recorded'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=per_day['day_recorded'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                math.ceil(per_day['amount_recorded'][i])
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()

        if milking_query_midday:
            for i in range(len(midday['amount'])):
                if i == 0:
                    if midday['diff'][i] != 0:
                        last_milking = midday['amount'][i] - \
                            (midday['amount'][i] * 0.2)

                        per_day = calculate_total_milk_v2(last_milking, midday['amount'][i], 0.2, midday['diff'][i],
                                                          midday['date'][i] - timedelta(days=midday['diff'][i]), midday['date'][i])
                        for i in range(len(per_day['day_recorded'])):

                            if per_day['day_recorded'][i].date() not in passed_days:

                                entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                      amount=math.ceil(
                                                          (per_day['amount_recorded'][i])),
                                                      num_of_animals_milked=1)

                                db.session.add(entry)
                                db.session.commit()
                                passed_days.append(
                                    per_day['day_recorded'][i].date())
                            else:
                                updated_date = MilkingPerDay.query.filter_by(
                                    date_recorded=per_day['day_recorded'][i].date()).first()
                                updated_date.amount = updated_date.amount + \
                                    math.ceil(per_day['amount_recorded'][i])
                                updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                                db.session.commit()
                    else:

                        # Add amount and date to milk_per_day table
                        if midday['date'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=midday['date'][i].date(),
                                                  amount=midday['amount'][i],
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(midday['date'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=midday['date'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                midday['amount'][i]
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()
                else:

                    per_day = calculate_total_milk_v2(midday['amount'][i-1], midday['amount'][i], midday['rate'][i], midday['diff'][i] - midday['diff'][i-1],
                                                      midday['date'][i-1], midday['date'][i])

                    for i in range(len(per_day['day_recorded'])):

                        if per_day['day_recorded'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                  amount=math.ceil(
                                                      per_day['amount_recorded'][i]),
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(
                                per_day['day_recorded'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=per_day['day_recorded'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                math.ceil(per_day['amount_recorded'][i])
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()

        if milking_query_evening:

            for i in range(len(evening['amount'])):
                if i == 0:
                    if evening['diff'][i] != 0:
                        last_milking = evening['amount'][i] - \
                            (evening['amount'][i] * 0.2)

                        per_day = calculate_total_milk_v2(last_milking, evening['amount'][i], 0.2, evening['diff'][i],
                                                          evening['date'][i] - timedelta(days=evening['diff'][i]), evening['date'][i])
                        for i in range(len(per_day['day_recorded'])):

                            if per_day['day_recorded'][i].date() not in passed_days:

                                entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                      amount=math.ceil((per_day['amount_recorded'][i]),
                                                      num_of_animals_milked=1),
                                                      )

                                db.session.add(entry)
                                db.session.commit()
                                passed_days.append(
                                    per_day['day_recorded'][i].date())
                            else:
                                updated_date = MilkingPerDay.query.filter_by(
                                    date_recorded=per_day['day_recorded'][i].date()).first()
                                updated_date.amount = updated_date.amount + \
                                    math.ceil(per_day['amount_recorded'][i])
                                updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                                db.session.commit()
                    else:

                        # Add amount and date to milk_per_day table
                        if evening['date'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=evening['date'][i].date(),
                                                  amount=evening['amount'][i],
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(evening['date'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=evening['date'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                evening['amount'][i]
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()
                else:

                    per_day = calculate_total_milk_v2(evening['amount'][i-1], evening['amount'][i], evening['rate'][i], evening['diff'][i] - evening['diff'][i-1],
                                                      evening['date'][i-1], evening['date'][i])

                    for i in range(len(per_day['day_recorded'])):

                        if per_day['day_recorded'][i].date() not in passed_days:

                            entry = MilkingPerDay(date_recorded=per_day['day_recorded'][i].date(),
                                                  amount=math.ceil(
                                                      per_day['amount_recorded'][i]),
                                                  num_of_animals_milked=1)

                            db.session.add(entry)
                            db.session.commit()
                            passed_days.append(
                                per_day['day_recorded'][i].date())
                        else:
                            updated_date = MilkingPerDay.query.filter_by(
                                date_recorded=per_day['day_recorded'][i].date()).first()
                            updated_date.amount = updated_date.amount + \
                                math.ceil(per_day['amount_recorded'][i])
                            updated_date.num_of_animals_milked = updated_date.num_of_animals_milked + 1
                            db.session.commit()

    return '<h1>'+str('All recorded have been updated!!!!')+'</h1>'


####################################################################
####################################################################
##################  End of Scripts Section  ########################
####################################################################

@ admin.route('/check_milking_params/<int:animal_id>', methods=['GET', 'POST'])
@ login_required
def check_milking_params(animal_id):
    q = AnimalMilkingPeriods.query \
        .filter(AnimalMilkingPeriods.animal_id == animal_id) \
        .filter(AnimalMilkingPeriods.end_of_milking_period == None) \
        .all()

    query = db.session.query(
        Milking.amount.label('amount'), cast(Milking.date_recorded, Date).label('dates')) \
        .filter(Milking.animal_id == animal_id) \
        .filter(Milking.milking_time == 'EVENING') \
        .distinct(cast(Milking.date_recorded, Date)) \
        .order_by(cast(Milking.date_recorded, Date).asc())

    dates = [item.dates for item in query]
    amounts = [item.amount for item in query]

    # Check if query has results
    if len(q) != 0 and len(q) == 1:
        result = 'OK'
        start_date = q[0].start_of_milking_period
        milking_period = q[0].milking_period
        d = date.today() - start_date
    else:
        result = 'Not active animal'
    return '<h1>'+str(result)+'</h1>'
