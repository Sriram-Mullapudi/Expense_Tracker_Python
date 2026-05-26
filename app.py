"""Main Flask application routes for InsightFlow (AI-Powered Expense Intelligence).

This module contains all route definitions. Application initialization
has been refactored into the factory.py module using the application
factory pattern for better testability, modularity, and configuration management.
"""
from typing import Optional
from flask import render_template, request, redirect, url_for, flash, Response, jsonify, send_from_directory, current_app
from flask_login import login_required, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timezone, timedelta
from sqlalchemy import func
import csv
import io
import os
import secrets
import logging
from pydantic import ValidationError

from factory import create_app
from models import db, User, Expense, Setting, Alert
from config import Config

# Export JWT_SECRET for tests and other modules
JWT_SECRET = Config.JWT_SECRET
from services import ExpenseService
from services.validators import (
    ExpenseCreateRequest, ExpenseUpdateRequest, ExpenseFilterRequest
)
from utils import (
    get_setting, set_setting, parse_month,
    calculate_today_total, calculate_month_total,
    get_monthly_budget, calculate_category_spending,
    check_budget_and_create_alerts, get_active_alerts
)
from sentry_config import add_breadcrumb
from email_service import send_username_recovery_email, send_alert_email, send_welcome_email
from analytics_service import (
    get_monthly_trends, get_category_breakdown, get_highest_spending_categories,
    get_daily_breakdown, get_spending_statistics, get_month_comparison
)
from file_upload_service import (
    save_upload_file, delete_upload_file, get_file_url, allowed_file,
    file_exists
)

# Create Flask application using factory pattern
app = create_app()

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete an expense."""
    try:
        result = ExpenseService.delete_expense(
            user_id=current_user.id,
            expense_id=int(id)
        )
        
        if result['success']:
            flash(result['message'], 'success')
        else:
            flash(result['message'], 'danger')
    
    except ValueError as ve:
        flash(str(ve), 'danger')
    except Exception as e:
        flash(f"Error: {str(e)}", 'danger')
    
    return redirect(url_for('index'))


@app.route('/export')
@login_required
def export_csv():
    """Export expenses to CSV file."""
    try:
        # Build filters dict
        filters = {
            'date_from': datetime.strptime(request.args.get('date_from'), '%Y-%m-%d').date() if request.args.get('date_from') else None,
            'date_to': datetime.strptime(request.args.get('date_to'), '%Y-%m-%d').date() if request.args.get('date_to') else None,
            'category': request.args.get('category') if request.args.get('category') and request.args.get('category').lower() != 'all' else None,
            'month': request.args.get('month')
        }
        
        # Call ExpenseService
        csv_data = ExpenseService.export_to_csv(
            user_id=current_user.id,
            filters=filters
        )
        
        resp = Response(csv_data, mimetype='text/csv')
        resp.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
        return resp
    
    except Exception as e:
        flash(f"Export error: {str(e)}", 'danger')
        return redirect(url_for('index'))


@app.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    """Manage user settings like monthly budget."""
    if request.method == 'POST':
        monthly_budget = request.form.get('monthly_budget') or ''
        set_setting('monthly_budget', monthly_budget)
        flash('Settings updated', 'success')
        return redirect(url_for('index'))

    current_budget = get_setting('monthly_budget') or ''
    month_total = calculate_month_total()
    
    budget_value = 0
    remaining_budget = 0
    if current_budget:
        try:
            budget_value = float(current_budget)
            remaining_budget = budget_value - month_total
        except ValueError:
            budget_value = 0
            remaining_budget = 0

    return render_template(
        'settings.html',
        monthly_budget=current_budget,
        budget_value=budget_value,
        month_total=month_total,
        remaining_budget=remaining_budget
    )
@app.route('/')
@login_required
def index():
    """Display dashboard with expenses and statistics."""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category', 'all')
    month = request.args.get('month')

    try:
        # Validate filters with Pydantic
        filters = ExpenseFilterRequest(
            date_from=datetime.strptime(date_from, '%Y-%m-%d').date() if date_from else None,
            date_to=datetime.strptime(date_to, '%Y-%m-%d').date() if date_to else None,
            category=category if category and category.lower() != 'all' else None,
            month=month
        )
        
        # Call ExpenseService for filtered list
        result = ExpenseService.list_expenses(
            user_id=current_user.id,
            date_from=filters.date_from,
            date_to=filters.date_to,
            category=filters.category,
            month=filters.month
        )
        
        if result['success']:
            expenses = result.get('expenses', [])
            total_spent = result.get('total', 0)
        else:
            expenses = []
            total_spent = 0
            flash(result.get('message', 'Error loading expenses'), 'warning')
    
    except ValidationError:
        expenses = []
        total_spent = 0
        flash('Invalid filter values', 'warning')
    except Exception as e:
        expenses = []
        total_spent = 0
        flash(f"Error: {str(e)}", 'danger')
    
    all_categories = [c[0] for c in db.session.query(Expense.category).filter_by(user_id=current_user.id).distinct().all()]
    
    filters_display = {
        'date_from': date_from or '',
        'date_to': date_to or '',
        'category': category,
        'month': month or ''
    }

    # Calculate statistics via service
    today_result = ExpenseService.get_today_total(current_user.id)
    today_total = today_result.get('today_total', 0)
    
    month_result = ExpenseService.get_month_total(current_user.id)
    month_total = month_result.get('month_total', 0)
    
    budget, budget_warning = get_monthly_budget()
    
    # Category spending breakdown via service
    category_result = ExpenseService.get_category_breakdown(current_user.id)
    if category_result['success']:
        breakdown = category_result.get('breakdown', {})
    else:
        breakdown = {}
    
    category_labels = list(breakdown.keys())
    category_values = list(breakdown.values())
    
    # Get active alerts
    active_alerts = get_active_alerts(current_user.id)

    return render_template('index.html', 
                         expenses=expenses, 
                         all_categories=all_categories, 
                         filters=filters_display,
                         total_spent=total_spent,
                         today_total=today_total,
                         month_total=month_total,
                         budget=budget,
                         budget_warning=budget_warning,
                         category_labels=category_labels,
                         category_values=category_values,
                         active_alerts=active_alerts)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validate input
        if not username or not password:
            flash('Username and password are required', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(username=username).first()

        if user is None:
            flash('Username not found. Please register first.', 'warning')
            return render_template('login.html')
        
        if not check_password_hash(user.password, password):
            flash('Invalid password. Please try again.', 'danger')
            return render_template('login.html')
        
        # Successfully authenticated
        login_user(user)
        flash(f'Welcome back, {username}!', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration route."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate input
        if not username or not email or not password:
            flash('All fields are required', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        # Check if username already exists
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return render_template('register.html')
        
        # Check if email already exists
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        # Create new user
        user = User(
            username=username,
            email=email,
            password=generate_password_hash(password)
        )
        db.session.add(user)
        db.session.commit()
        
        # Send welcome email
        send_welcome_email(user.email, user.username)
        
        # Log in the user
        login_user(user)
        flash('Account created successfully! Welcome!', 'success')
        return redirect(url_for('index'))
    
    return render_template('register.html')

@app.route('/forgot-username', methods=['GET', 'POST'])
def forgot_username():
    """Forgot username route."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        
        if not email:
            flash('Email is required', 'danger')
            return render_template('forgot_username.html')
        
        user = User.query.filter_by(email=email).first()
        if user:
            send_username_recovery_email(user.email, user.username)
            flash('Username sent to your email.', 'info')
        else:
            flash('If an account with that email exists, your username has been sent.', 'info')
        
        return redirect(url_for('login'))
    
    return render_template('forgot_username.html')

@app.route('/logout')
@login_required
def logout():
    """User logout route."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new expense."""
    if request.method == 'POST':
        try:
            # Parse & Validate with Pydantic
            expense_data = ExpenseCreateRequest(
                title=request.form.get('title', '').strip(),
                category=request.form.get('category', '').strip(),
                amount=float(request.form.get('amount', 0)),
                description=request.form.get('description', '').strip(),
                date=datetime.strptime(
                    request.form.get('date', ''),
                    '%Y-%m-%d'
                ).date()
            )
            
            # Call ExpenseService
            result = ExpenseService.create_expense(
                user_id=current_user.id,
                title=expense_data.title,
                category=expense_data.category,
                amount=expense_data.amount,
                date_obj=expense_data.date,
                description=expense_data.description
            )
            
            if result['success']:
                # Check budget alerts
                alert = check_budget_and_create_alerts(current_user.id)
                if alert:
                    severity = 'danger' if alert.severity == 'danger' else 'warning'
                    flash(f'⚠️ {alert.title}: {alert.message}', severity)
                
                flash(result['message'], 'success')
                return redirect(url_for('index'))
        
        except ValidationError as ve:
            errors = ve.errors()
            flash(f"Validation error: {errors[0]['msg']}", 'danger')
        except ValueError as ve:
            flash(str(ve), 'danger')
        except Exception as e:
            flash(f"Error: {str(e)}", 'danger')

    return render_template('add.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit an existing expense."""
    if request.method == 'POST':
        try:
            # Parse & Validate with Pydantic
            expense_data = ExpenseUpdateRequest(
                title=request.form.get('title', '').strip() or None,
                category=request.form.get('category', '').strip() or None,
                amount=float(request.form.get('amount')) if request.form.get('amount') else None,
                description=request.form.get('description', '').strip() or None,
                date=datetime.strptime(
                    request.form.get('date', ''),
                    '%Y-%m-%d'
                ).date() if request.form.get('date') else None
            )
            
            # Call ExpenseService
            result = ExpenseService.update_expense(
                user_id=current_user.id,
                expense_id=int(id),
                **{k: v for k, v in expense_data.dict().items() if v is not None}
            )
            
            if result['success']:
                flash(result['message'], 'success')
                return redirect(url_for('index'))
        
        except ValidationError as ve:
            errors = ve.errors()
            flash(f"Validation error: {errors[0]['msg']}", 'danger')
        except ValueError as ve:
            flash(str(ve), 'danger')
        except Exception as e:
            flash(f"Error: {str(e)}", 'danger')
    
    # GET: Fetch expense for editing
    try:
        result = ExpenseService.get_expense(
            user_id=current_user.id,
            expense_id=int(id)
        )
        if result['success']:
            return render_template('edit.html', expense=result['expense'])
        else:
            flash(result['message'], 'danger')
            return redirect(url_for('index'))
    except Exception as e:
        flash(str(e), 'danger')
        return redirect(url_for('index'))


@app.route('/api/dashboard-stats')
@login_required
def api_dashboard_stats():
    """API endpoint for dynamic dashboard statistics."""
    today_total = calculate_today_total()
    month_total = calculate_month_total()
    budget, budget_warning = get_monthly_budget()
    
    return jsonify({
        'today_total': round(today_total, 2),
        'month_total': round(month_total, 2),
        'budget': round(budget, 2),
        'budget_warning': budget_warning,
        'remaining_budget': round(budget - month_total, 2) if budget > 0 else 0
    })


# ============ ANALYTICS ROUTES ============

@app.route('/analytics')
@login_required
def analytics():
    """Analytics dashboard page."""
    return render_template('analytics.html')


@app.route('/api/analytics/trends')
@login_required
def api_analytics_trends():
    """Get monthly spending trends."""
    months = request.args.get('months', 12, type=int)
    trends = get_monthly_trends(current_user.id, min(months, 24))
    return jsonify(trends)


@app.route('/api/analytics/categories')
@login_required
def api_analytics_categories():
    """Get category breakdown."""
    months = request.args.get('months', 1, type=int)
    breakdown, total = get_category_breakdown(current_user.id, min(months, 12))
    return jsonify({'breakdown': breakdown, 'total': round(total, 2)})


@app.route('/api/analytics/top-categories')
@login_required
def api_analytics_top_categories():
    """Get top spending categories."""
    limit = request.args.get('limit', 5, type=int)
    months = request.args.get('months', 1, type=int)
    top_cats = get_highest_spending_categories(current_user.id, min(limit, 10), min(months, 12))
    return jsonify(top_cats)


@app.route('/api/analytics/daily')
@login_required
def api_analytics_daily():
    """Get daily spending breakdown."""
    month = request.args.get('month', None)
    daily = get_daily_breakdown(current_user.id, month)
    return jsonify(daily)


@app.route('/api/analytics/stats')
@login_required
def api_analytics_stats():
    """Get spending statistics."""
    months = request.args.get('months', 1, type=int)
    stats = get_spending_statistics(current_user.id, min(months, 12))
    return jsonify({k: round(v, 2) for k, v in stats.items()})


@app.route('/api/analytics/comparison')
@login_required
def api_analytics_comparison():
    """Get month-over-month comparison."""
    comparison = get_month_comparison(current_user.id)
    return jsonify(comparison)


# ============ FILE UPLOAD ROUTES ============

@app.route('/api/upload/receipt', methods=['POST'])
@login_required
def api_upload_receipt():
    """Upload receipt file for an expense."""
    expense_id = request.form.get('expense_id', type=int)
    
    if not expense_id:
        return jsonify({'error': 'Missing expense_id'}), 400
    
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != current_user.id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    filename, error = save_upload_file(file, current_user.id)
    
    if error:
        return jsonify({'error': error}), 400
    
    # Delete old receipt if exists
    if expense.receipt_path:
        delete_upload_file(expense.receipt_path)
    
    # Update expense with new receipt
    expense.receipt_path = filename
    db.session.commit()
    
    return jsonify({
        'success': True,
        'filename': filename,
        'url': get_file_url(filename)
    }), 201


@app.route('/uploads/receipts/<filename>')
@login_required
def serve_receipt(filename):
    """Serve uploaded receipt file."""
    # Security: verify user owns this file
    # Files are named with user_id, so check prefix
    if not filename.startswith(f"{current_user.id}_"):
        flash('Unauthorized', 'warning')
        return redirect(url_for('index'))
    
    if not file_exists(filename):
        flash('File not found', 'danger')
        return redirect(url_for('index'))
    
    return send_from_directory('uploads/receipts', filename)


@app.route('/api/upload/delete-receipt/<int:expense_id>', methods=['POST'])
@login_required
def api_delete_receipt(expense_id):
    """Delete receipt file from expense."""
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != current_user.id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if expense.receipt_path:
        delete_upload_file(expense.receipt_path)
        expense.receipt_path = None
        db.session.commit()
        return jsonify({'success': True}), 200
    
    return jsonify({'error': 'No receipt attached'}), 400


# ============ ROLE-BASED ACCESS ROUTES ============

def admin_required(f):
    """Decorator for admin-only routes."""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first', 'warning')
            return redirect(url_for('login'))
        
        if not current_user.is_admin():
            flash('You do not have permission to access this page', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    
    return decorated_function


@app.route('/admin')
@admin_required
def admin_dashboard():
    """Admin dashboard page."""
    total_users = User.query.count()
    total_expenses = Expense.query.count()
    total_amount = db.session.query(func.sum(Expense.amount)).scalar() or 0
    
    # Get all users with expense count
    users = db.session.query(
        User,
        func.count(Expense.id).label('expense_count'),
        func.sum(Expense.amount).label('total_amount')
    ).outerjoin(Expense).group_by(User.id).all()
    
    return render_template(
        'admin.html',
        total_users=total_users,
        total_expenses=total_expenses,
        total_amount=round(total_amount, 2),
        users=users
    )


@app.route('/api/admin/users')
@admin_required
def api_admin_users():
    """Get all users for admin."""
    users = db.session.query(
        User,
        func.count(Expense.id).label('expense_count'),
        func.sum(Expense.amount).label('total_amount')
    ).outerjoin(Expense).group_by(User.id).all()
    
    user_data = []
    for user, expense_count, total_amount in users:
        user_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'role': user.role,
            'created_at': user.created_at.isoformat() if user.created_at else None,
            'expense_count': expense_count or 0,
            'total_amount': float(total_amount) if total_amount else 0
        })
    
    return jsonify(user_data)


@app.route('/api/admin/stats')
@admin_required
def api_admin_stats():
    """Get system-wide statistics."""
    
    total_users = User.query.count()
    total_expenses = Expense.query.count()
    total_amount = db.session.query(func.sum(Expense.amount)).scalar() or 0
    
    # Calculate average spending per user
    user_totals_subq = db.session.query(
        func.sum(Expense.amount).label('user_total')
    ).group_by(Expense.user_id).subquery()
    
    avg_per_user = db.session.query(func.avg(user_totals_subq.c.user_total)).scalar() or 0
    
    total_alerts = Alert.query.count()
    active_alerts = Alert.query.filter_by(is_read=False).count()
    
    return jsonify({
        'total_users': total_users,
        'total_expenses': total_expenses,
        'total_amount': round(float(total_amount), 2),
        'average_per_user': round(float(avg_per_user), 2),
        'total_alerts': total_alerts,
        'active_alerts': active_alerts
    })


@app.route('/api/admin/promote-admin/<int:user_id>', methods=['POST'])
@admin_required
def api_promote_admin(user_id):
    """Promote user to admin."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.role = 'admin'
    db.session.commit()
    
    flash(f'User {user.username} promoted to admin', 'success')
    return jsonify({'success': True}), 200


@app.route('/api/admin/demote-admin/<int:user_id>', methods=['POST'])
@admin_required
def api_demote_admin(user_id):
    """Demote admin to regular user."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent demoting self
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot demote yourself'}), 400
    
    user.role = 'user'
    db.session.commit()
    
    flash(f'User {user.username} demoted to regular user', 'success')
    return jsonify({'success': True}), 200


@app.route('/api/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def api_delete_user(user_id):
    """Delete a user and all their data."""
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting self
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    username = user.username
    
    # Delete related data (cascade will handle it)
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} and all their data deleted', 'success')
    return jsonify({'success': True}), 200


if __name__ == '__main__':
    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)