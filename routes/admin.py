"""Admin routes for system management."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from functools import wraps
from models import db, User, Expense
from datetime import datetime

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


def admin_required(f):
    """Decorator for admin-only routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in first', 'warning')
            return redirect(url_for('auth.login'))
        
        if not current_user.is_admin():
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard.index'))
        
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@admin_required
def dashboard():
    """Admin dashboard."""
    user_count = User.query.count()
    expense_count = Expense.query.count()
    total_spending = db.session.query(db.func.sum(Expense.amount)).scalar() or 0
    avg_expense = db.session.query(db.func.avg(Expense.amount)).scalar() or 0
    
    recent_users = User.query.order_by(User.created_at.desc()).limit(10).all()
    recent_expenses = Expense.query.order_by(Expense.created_at.desc()).limit(10).all()
    
    return render_template(
        'admin.html',
        user_count=user_count,
        expense_count=expense_count,
        total_spending=round(total_spending, 2),
        avg_expense=round(avg_expense, 2),
        recent_users=recent_users,
        recent_expenses=recent_expenses
    )


@admin_bp.route('/users')
@admin_required
def users():
    """List all users."""
    page = request.args.get('page', 1, type=int)
    users = User.query.paginate(page=page, per_page=20)
    return render_template('admin_users.html', users=users)


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@admin_required
def toggle_admin(user_id):
    """Toggle admin status for a user."""
    if user_id == current_user.id:
        flash('Cannot change your own admin status', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    user.role = 'admin' if user.role == 'user' else 'user'
    db.session.commit()
    
    flash(f'User {user.username} admin status updated', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user and their data."""
    if user_id == current_user.id:
        flash('Cannot delete your own account', 'danger')
        return redirect(url_for('admin.users'))
    
    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    
    flash(f'User {username} deleted', 'info')
    return redirect(url_for('admin.users'))


@admin_bp.route('/api/stats', methods=['GET'])
@admin_required
def api_stats():
    """Get admin statistics."""
    stats = {
        'total_users': User.query.count(),
        'total_expenses': Expense.query.count(),
        'total_spending': round(db.session.query(db.func.sum(Expense.amount)).scalar() or 0, 2),
        'avg_expense': round(db.session.query(db.func.avg(Expense.amount)).scalar() or 0, 2),
    }
    return jsonify(stats)
