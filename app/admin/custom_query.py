from random import randint
from faker import Faker
import os
import psycopg2
from sqlalchemy import true
import random

# establishing the connection
conn = psycopg2.connect(
    database=os.environ.get("DATABASE_NAME"),
    user=os.environ.get("DATABASE_USER"),
    password=os.environ.get("DATABASE_PASSWORD"),
    host=os.environ.get("DATABASE_HOST"),
    port=os.environ.get("DATABASE_PORT")
)

fake = Faker()


def getMilkingData(animal_id, selected_year):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    # when a query produces an error and you try to run another query without first rolling back the transaction,
    # it says PSQLException: current transaction is aborted, commands ignored until end of transaction block
    cursor.execute("ROLLBACK")

    # Retrieving only sum of milking per animal and per year

    cursor.execute('''
        with first_table as (
            select distinct date_recorded as animal_date,
                    ROUND((sum(total)/1000)::NUMERIC,2) as animal_total,
                    (
                    ROUND((((SUM(total) * 1.0 - LAG(SUM(total))  OVER (ORDER BY date_recorded::DATE))/
                    LAG(SUM(total)) OVER (ORDER BY date_recorded::DATE)
                    )*100)::NUMERIC,2)
                    ) AS Change,
                    days_from_last_birth
            from (
                select date_recorded::DATE, sum(amount) as total, days_from_last_birth
                
                from milkings
                where animal_id=%s and milking_period=%s
                group by date_recorded, days_from_last_birth

            ) as t1
            GROUP BY t1.date_recorded, t1.days_from_last_birth
            ORDER BY t1.date_recorded ASC
            ),
            second_table as
            (
                select distinct date_recorded as stable_date, ROUND((sum(total)/1000)::NUMERIC,2) as total_stable
            from (
                select date_recorded::DATE, sum(amount) as total
                from milkings
                where milking_period = %s
                group by date_recorded
            ) as t2
            group by t2.date_recorded
            order by t2.date_recorded asc
            ),
            third_table as (
                SELECT date_recorded::date as num_date, count(DISTINCT animal_id) num_of_animals
            FROM milkings
            where milking_period=%s
            GROUP BY date_recorded::date
            )
            select animal_date, animal_total, change, days_from_last_birth, 
            total_stable, num_of_animals, ROUND((total_stable/num_of_animals)::NUMERIC,2) as avg_milk,
            ROUND(((animal_total/total_stable)*100)::NUMERIC,2) as percent_of_animal
            from first_table
            join second_table on first_table.animal_date = second_table.stable_date
            join third_table on first_table.animal_date = third_table.num_date
    ''', [animal_id, selected_year, selected_year, selected_year])

    updated_result = cursor.fetchall()
    print(updated_result)

    cursor.close()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def get_statistics_query(animal_id):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    cursor.execute("ROLLBACK")
    # Retrieving only sum of milking per animal and per year

    cursor.execute('''

        with first_table as 
            (
            select
            DISTINCT to_char(date_recorded,'yyyy-MM-dd') AS distinct_dates,
            date_part('week', date_recorded::date)::INTEGER AS animal_weekly,
            date_part('year', date_recorded::date)::INTEGER AS animal_yearly,
            sum(amount/1000)::NUMERIC(10,2) as animal_sum  --- total milking from all animals

            from milkings
                where animal_id = %s
            group by animal_weekly, animal_yearly, distinct_dates
            order by animal_yearly, animal_weekly
            ),

            second_table as
            (
            select b.parent_id, b.child_id, u.date_of_birth,
                extract(year from u.date_of_birth)::INTEGER as bday
                from animal_births b
                join animals u on b.child_id = u.id
                where b.parent_id = %s
            ), third_table as
            (
                select * from
            (
            select 
            date_part('week', date_recorded::date)::INTEGER AS weekly,
            date_part('year', date_recorded::date)::INTEGER AS yearly,
            sum(amount/1000)::NUMERIC(10,2) as total_sum,  --- total milking from all animals
            round(sum(amount/1000)::NUMERIC(10,2)/count(distinct(animal_id)),2) as total_avg
            from milkings 
            group by weekly, yearly
            order by yearly, weekly
            ) as choice
            ), 
            fourth_table as (
                (
                        WITH weekly_amounts as (
                        SELECT date_part('year', date_recorded::date)::INTEGER as yearly,
                        date_part('week', date_recorded::date)::INTEGER AS weekly,
                        date_part('month',date_recorded::date)::INTEGER AS monthly,
                        ROUND(SUM(amount/1000)::numeric,2) as amount          
                        FROM milkings
                        WHERE animal_id=%s
                        GROUP BY yearly, weekly, monthly
                        ORDER BY yearly, weekly, monthly
                        )
                    
                        SELECT weekly AS "week", yearly as "yearly", SUM(amount) AS "amount", 
                            (
                                ROUND(((SUM(amount) * 1.0 - LAG(SUM(amount))  OVER (ORDER BY yearly,weekly))/
                                LAG(SUM(amount)) OVER (ORDER BY yearly, weekly)
                                )*100::NUMERIC,2)) AS Change
                        FROM weekly_amounts
                        GROUP BY week,yearly
                        ORDER BY yearly, week
                        
            ))

            SELECT parent_id,child_id,date_of_birth,distinct_dates,animal_weekly,animal_yearly,animal_sum,total_sum,total_avg,amount,Change,distinct_dates::date - date_of_birth::date  as days from second_table 
            inner join first_table on first_table.animal_yearly = second_table.bday
            inner join third_table on third_table.weekly = first_table.animal_weekly
            and third_table.yearly = second_table.bday
            join fourth_table on fourth_table.week = first_table.animal_weekly
            and fourth_table.yearly = second_table.bday



        
    ''', [animal_id, animal_id, animal_id])

    updated_result = cursor.fetchall()
    cursor.close()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def get_last_birth(id):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    cursor.execute("ROLLBACK")
    # Retrieving only sum of milking per animal and per year

    cursor.execute('''
        select b.parent_id, b.child_id, u.date_of_birth, b.milking_period
        from animal_births b
        join animals u on b.child_id = u.id
        where b.parent_id = %s
        ORDER BY u.date_of_birth DESC LIMIT 1
    ''', [id])

    updated_result = cursor.fetchall()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def get_percentage_change_of_milkings_data(animal_id, selected_year):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    cursor.execute("ROLLBACK")
    # Retrieving only sum of milking per animal and per year
    cursor.execute('''
        WITH weekly_amounts as (
                SELECT date_part('year', date_recorded::date) as yearly,
                date_part('week', date_recorded::date) AS weekly,
                date_part('month',date_recorded::date) AS monthly,
                ROUND(SUM(amount)::numeric,2) as amount          
            FROM milkings
            WHERE animal_id=%s and extract(year from date_recorded)=%s
            GROUP BY yearly, weekly, monthly
            ORDER BY yearly, weekly, monthly
        )

        SELECT weekly AS "week", yearly as "yearly", SUM(amount) AS "amount", 
            (
                ROUND(((SUM(amount) * 1.0 - LAG(SUM(amount))  OVER (ORDER BY yearly,weekly))/
                LAG(SUM(amount)) OVER (ORDER BY yearly, weekly)
                )*100::NUMERIC,2)) AS "Change"
        FROM weekly_amounts
        GROUP BY week,yearly
        ORDER BY yearly, week
    ''', [animal_id, selected_year])

    updated_result = cursor.fetchall()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def income_per_month(selected_year):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    cursor.execute("ROLLBACK")
    # Retrieving only sum of milking per animal and per year

    cursor.execute('''
        select 
            date_trunc('month', date_recorded) as num_mon,
            to_char(date_recorded,'Mon') as mon,
            ROUND( sum(amount)::numeric, 1 ) as total
        from incomes
        WHERE extract(year from date_recorded)=%s
        group by 1,2
        ORDER BY num_mon
    ''', [selected_year])

    updated_result = cursor.fetchall()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def expense_per_month(selected_year):

    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()
    cursor.execute("ROLLBACK")
    # Retrieving only sum of milking per animal and per year

    cursor.execute('''
        select 
            date_trunc('month', date_recorded) as num_mon,
            to_char(date_recorded,'Mon') as mon,
            ROUND( sum(amount)::numeric, 1 ) as total
        from expenses
        WHERE extract(year from date_recorded)=%s
        group by 1,2
        ORDER BY num_mon
    ''', [selected_year])

    updated_result = cursor.fetchall()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result


def income_vs_expense(selected_year):
    cursor.execute("ROLLBACK")
    # Creating a cursor object using the cursor()
    # method
    cursor = conn.cursor()

    # Retrieving only sum of milking per animal and per year

    cursor.execute('''
        SELECT (SELECT ROUND( sum(incomes.amount)::numeric, 1 ) as income_total from incomes WHERE extract(year from incomes.date_recorded)=%s) AS income,
       (SELECT ROUND( sum(expenses.amount)::numeric, 1 ) as expense_total from expenses WHERE extract(year from expenses.date_recorded)=%s) AS expense;
    ''', [selected_year, selected_year])

    updated_result = cursor.fetchall()

    # Commit your changes in the database
    conn.commit()

    # Closing the connection
    # conn.close()

    return updated_result
