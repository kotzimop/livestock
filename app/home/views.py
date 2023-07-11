# app/home/views.py

from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user, login_required

home = Blueprint('home', __name__)


@home.route('/')
@login_required
def homepage():
    """
    Render the homepage template on the / route
    """
    return redirect(url_for('admin.list_data'))


@home.route('/dashboard')
@login_required
def dashboard():
    """
    Render the dashboard template on the /dashboard route
    """
    return render_template('home/dashboard.html', title="Dashboard")

# add admin dashboard view


@home.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # prevent non-admins from accessing the page
    if not current_user.is_admin:
        # abort(403)
        return render_template('home/page-403.html'), 403

    return render_template('home/new_admin.html', title="Dashboard")
