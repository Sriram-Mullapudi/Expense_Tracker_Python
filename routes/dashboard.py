"""Dashboard and expense management routes."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import func
import csv
import io
from models import db, Expense, Setting
from utils import (
    parse_month, calculate_month_total, get_setting, set_setting,
    calculate_category_spending, check_budget_and_create_alerts
)
from analytics_service import (
    get_monthly_trends, get_category_breakdown, get_spending_statistics,
    get_month_comparison, get_daily_breakdown
)

dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/')


@dashboard_bp.route('/')
@login_required
def index():
    """Display dashboard with expenses and statistics."""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category', 'all')
    month = request.args.get('month')

    q = Expense.query.filter_by(user_id=current_user.id)

    if month:
        first, last = parse_month(month)
        if first and last:
            q = q.filter(Expense.date >= first, Expense.date <= last)

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except ValueError:
            pass

    if category and category.lower() != 'all':
        q = q.filter_by(category=category)

    items = q.order_by(Expense.date.desc()).all()
    
    # Calculate totals - use Decimal(0) as start value to ensure type consistency
    total = sum((e.amount for e in items), Decimal(0))
    
    # Calculate today's spending
    today_spending = sum((e.amount for e in items if e.date == date.today()), Decimal(0))
    
    category_spending = calculate_category_spending(items)
    category_labels = list(category_spending.keys())
    # Convert Decimal values to float for JSON serialization in templates
    category_values = [float(v) for v in category_spending.values()]
    # Also convert category_spending dict itself for template use
    category_spending_float = {k: float(v) for k, v in category_spending.items()}
    
    month_total = calculate_month_total(current_user.id)
    budget = get_setting('monthly_budget')
    budget_value = float(budget) if budget else 0
    remaining_budget = budget_value - float(month_total) if budget_value else None
    
    # Get all categories for filter dropdown
    all_expenses = Expense.query.filter_by(user_id=current_user.id).all()
    all_categories = sorted(set(e.category for e in all_expenses if e.category))
    
    active_alerts = current_user.alerts

    return render_template(
        'index.html',
        expenses=items,
        total_spent=float(total),
        today_total=float(today_spending),
        category_spending=category_spending_float,
        category_labels=category_labels,
        category_values=category_values,
        month_total=month_total,
        budget=budget_value,
        remaining_budget=remaining_budget,
        alerts=active_alerts,
        all_categories=all_categories,
        filters={
            'date_from': date_from,
            'date_to': date_to,
            'category': category,
            'month': month
        }
    )


@dashboard_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    """Add a new expense."""
    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        amount = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()

        # Validation
        if not all([date_str, title, category, amount]):
            flash('Date, title, category, and amount are required', 'danger')
            return render_template('add.html')

        try:
            expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            amount_float = float(amount)
            
            if amount_float <= 0:
                flash('Amount must be positive', 'danger')
                return render_template('add.html')

            expense = Expense(
                user_id=current_user.id,
                date=expense_date,
                title=title,
                category=category,
                amount=amount_float,
                description=description
            )
            db.session.add(expense)
            db.session.commit()
            
            # Check budget after adding expense
            alert = check_budget_and_create_alerts(current_user.id)
            if alert:
                severity_class = 'danger' if alert.severity == 'danger' else 'warning'
                flash(f'{alert.title}: {alert.message}', severity_class)
            
            flash('Expense added successfully', 'success')
            return redirect(url_for('dashboard.index'))
        except ValueError:
            flash('Invalid date or amount format', 'danger')

    return render_template('add.html')


@dashboard_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    """Edit an existing expense."""
    expense = Expense.query.get_or_404(id)
    
    if expense.user_id != current_user.id:
        flash('Unauthorized', 'danger')
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        date_str = request.form.get('date', '').strip()
        title = request.form.get('title', '').strip()
        category = request.form.get('category', '').strip()
        amount = request.form.get('amount', '').strip()
        description = request.form.get('description', '').strip()

        if not all([date_str, title, category, amount]):
            flash('Date, title, category, and amount are required', 'danger')
            return render_template('edit.html', expense=expense)

        try:
            expense.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            expense.title = title
            expense.category = category
            expense.amount = float(amount)
            expense.description = description
            
            if expense.amount <= 0:
                flash('Amount must be positive', 'danger')
                return render_template('edit.html', expense=expense)
            
            db.session.commit()
            flash('Expense updated successfully', 'success')
            return redirect(url_for('dashboard.index'))
        except ValueError:
            flash('Invalid date or amount format', 'danger')

    return render_template('edit.html', expense=expense)


@dashboard_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    """Delete an expense."""
    try:
        print(f"\n[DELETE] Starting delete for expense ID: {id}, User: {current_user.id}")
        
        expense = Expense.query.get_or_404(id)
        print(f"[DELETE] Found expense: {expense}")

        if expense.user_id != current_user.id:
            print(f"[DELETE] Ownership check FAILED: expense.user_id={expense.user_id}, current_user.id={current_user.id}")
            flash('Unauthorized', 'danger')
            return redirect(url_for('dashboard.index'))

        print(f"[DELETE] Ownership check passed, deleting expense...")
        db.session.delete(expense)
        print(f"[DELETE] Expense deleted from session")
        
        db.session.commit()
        print(f"[DELETE] Transaction committed successfully")
        
        flash('Expense deleted', 'info')
        print(f"[DELETE] Flash message set, redirecting to index")
        return redirect(url_for('dashboard.index'))
        
    except Exception as e:
        db.session.rollback()
        import traceback
        error_msg = str(e)
        traceback_str = traceback.format_exc()
        print(f"\n[DELETE ERROR] Exception occurred: {error_msg}")
        print(f"[DELETE TRACEBACK]\n{traceback_str}\n")
        flash(f'Error deleting expense: {error_msg}', 'danger')
        return redirect(url_for('dashboard.index'))


@dashboard_bp.route('/export')
@login_required
def export():
    """Export expenses to CSV file."""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    month = request.args.get('month')

    q = Expense.query.filter_by(user_id=current_user.id)

    if month:
        first, last = parse_month(month)
        if first and last:
            q = q.filter(Expense.date >= first, Expense.date <= last)

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except ValueError:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except ValueError:
            pass

    if category and category.lower() != 'all':
        q = q.filter_by(category=category)

    items = q.order_by(Expense.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'date', 'title', 'category', 'amount', 'description'])

    for item in items:
        writer.writerow([
            item.id,
            item.date.isoformat(),
            item.title,
            item.category,
            f"{item.amount:.2f}",
            item.description or ''
        ])

    resp = Response(output.getvalue(), mimetype='text/csv')
    resp.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    return resp


@dashboard_bp.route('/settings', methods=['GET', 'POST'])
@login_required
def settings():
    """Manage user settings like monthly budget."""
    if request.method == 'POST':
        monthly_budget = request.form.get('monthly_budget', '').strip()
        
        if monthly_budget:
            try:
                float(monthly_budget)
            except ValueError:
                flash('Invalid budget amount', 'danger')
                return redirect(url_for('dashboard.settings'))
        
        set_setting('monthly_budget', monthly_budget)
        flash('Settings updated', 'success')
        return redirect(url_for('dashboard.settings'))

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

    return render_template(
        'settings.html',
        monthly_budget=current_budget,
        budget_value=budget_value,
        month_total=month_total,
        remaining_budget=remaining_budget
    )
