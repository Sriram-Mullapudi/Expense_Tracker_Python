"""API routes with JWT authentication for InsightFlow AI platform."""
from typing import Callable, Optional, Dict, Any, Tuple
from flask import Blueprint, request, jsonify, current_app, Response
from functools import wraps
import jwt
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash, generate_password_hash
from models import db, User, Expense, Alert, Setting
from utils import calculate_today_total, calculate_month_total, get_monthly_budget, check_budget_and_create_alerts, get_active_alerts
from analytics_service import (
    get_monthly_trends, get_category_breakdown, get_highest_spending_categories,
    get_daily_breakdown, get_spending_statistics, get_month_comparison
)
from file_upload_service import save_upload_file, delete_upload_file, get_file_url

api_bp: Blueprint = Blueprint('api', __name__, url_prefix='/api')

# JWT Configuration - will be imported from app when initialized
JWT_SECRET: Optional[str] = None
JWT_EXPIRATION_HOURS: int = 24


def set_jwt_secret(secret: str) -> None:
    """
    Set JWT secret (called from app.py).
    
    Args:
        secret: Secret key for JWT encoding/decoding
    """
    global JWT_SECRET
    JWT_SECRET = secret


def token_required(f: Callable) -> Callable:
    """
    Decorator to require valid JWT token for API endpoints.
    
    Validates JWT token from Authorization header and sets request.current_user_id
    and request.current_user. Returns 401 error if token is missing, invalid, or expired.
    
    Args:
        f: Flask route function to decorate
    
    Returns:
        Decorated function that validates token before executing route
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Check for token in headers
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'message': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Invalid token'}), 401
        
        request.current_user_id = current_user_id
        request.current_user = db.session.get(User, current_user_id)
        
        if not request.current_user:
            return jsonify({'message': 'User not found'}), 401
        
        return f(*args, **kwargs)
    
    return decorated


@api_bp.route('/auth/register', methods=['POST'])
def register() -> Tuple[Dict[str, str], int]:
    """
    Register a new user via API.
    
    Request JSON:
        username: str - Unique username for account
        password: str - User password
        email: str - User email (optional)
    
    Returns:
        Tuple of (response_dict, status_code):
            201: User created successfully
            400: Missing required fields or username already exists
    """
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400
    
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400
    
    user = User(
        username=data['username'],
        password=generate_password_hash(data['password'])
    )
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'message': 'User created successfully'}), 201


@api_bp.route('/auth/login', methods=['POST'])
def login() -> Tuple[Dict[str, Any], int]:
    """
    Login user and return JWT token.
    
    Request JSON:
        username: str - User username
        password: str - User password
    
    Returns:
        Tuple of (response_dict, status_code):
            200: Login successful, returns JWT token
            400: Missing required fields
            401: Invalid credentials
    """
    data = request.get_json()
    
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'message': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not check_password_hash(user.password, data['password']):
        return jsonify({'message': 'Invalid credentials'}), 401
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'exp': datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    }, JWT_SECRET, algorithm='HS256')
    
    return jsonify({
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username
        }
    }), 200


@api_bp.route('/expenses', methods=['GET'])
@token_required
def get_expenses() -> Tuple[Dict[str, Any], int]:
    """
    Get all expenses for authenticated user.
    
    Requires: Valid JWT token in Authorization header
    
    Returns:
        Tuple of (response_list, status_code):
            200: List of expenses as JSON
    """
    expenses = Expense.query.filter_by(user_id=request.current_user_id).order_by(Expense.date.desc()).all()
    
    return jsonify([{
        'id': e.id,
        'date': e.date.isoformat(),
        'title': e.title,
        'category': e.category,
        'amount': float(e.amount),
        'description': e.description
    } for e in expenses]), 200


@api_bp.route('/expenses', methods=['POST'])
@token_required
def create_expense() -> Tuple[Dict[str, Any], int]:
    """
    Create a new expense for authenticated user.
    
    Request JSON:
        date: str - Expense date (YYYY-MM-DD format)
        title: str - Expense title
        category: str - Expense category
        amount: float - Expense amount
        description: str - Optional description
    
    Returns:
        Tuple of (response_dict, status_code):
            201: Expense created successfully
            400: Missing required fields or invalid format
    """
    data = request.get_json()
    
    required_fields = ['date', 'title', 'category', 'amount']
    if not all(field in data for field in required_fields):
        return jsonify({'message': 'Missing required fields'}), 400
    
    try:
        expense_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        amount = float(data['amount'])
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid date or amount format'}), 400
    
    expense = Expense(
        user_id=request.current_user_id,
        date=expense_date,
        title=data['title'],
        category=data['category'],
        amount=amount,
        description=data.get('description', '')
    )
    
    db.session.add(expense)
    db.session.commit()
    
    return jsonify({
        'id': expense.id,
        'message': 'Expense created successfully'
    }), 201


@api_bp.route('/expenses/<int:expense_id>', methods=['GET'])
@token_required
def get_expense(expense_id: int) -> Tuple[Dict[str, Any], int]:
    """
    Get a specific expense by ID.
    
    Args:
        expense_id: ID of expense to retrieve
    
    Returns:
        Tuple of (response_dict, status_code):
            200: Expense details
            403: Expense belongs to different user
            404: Expense not found
    """
    expense = Expense.query.get_or_404(expense_id)
    
    if expense.user_id != request.current_user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    
    return jsonify({
        'id': expense.id,
        'date': expense.date.isoformat(),
        'title': expense.title,
        'category': expense.category,
        'amount': float(expense.amount),
        'description': expense.description
    }), 200


@api_bp.route('/expenses/<int:expense_id>', methods=['PUT'])
@token_required
def update_expense(expense_id: int) -> Tuple[Dict[str, str], int]:
    """
    Update an expense.
    
    Args:
        expense_id: ID of expense to update
    
    Request JSON:
        date: str - New date (optional)
        title: str - New title (optional)
        category: str - New category (optional)
        amount: float - New amount (optional)
        description: str - New description (optional)
    
    Returns:
        Tuple of (response_dict, status_code):
            200: Expense updated successfully
            400: Invalid data format
            403: Expense belongs to different user
            404: Expense not found
    """
    expense = Expense.query.get_or_404(expense_id)
    
    if expense.user_id != request.current_user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    
    data = request.get_json()
    
    try:
        if 'date' in data:
            expense.date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        if 'title' in data:
            expense.title = data['title']
        if 'category' in data:
            expense.category = data['category']
        if 'amount' in data:
            expense.amount = float(data['amount'])
        if 'description' in data:
            expense.description = data['description']
        
        db.session.commit()
    except (ValueError, TypeError):
        return jsonify({'message': 'Invalid data format'}), 400
    
    return jsonify({'message': 'Expense updated successfully'}), 200


@api_bp.route('/expenses/<int:expense_id>', methods=['DELETE'])
@token_required
def delete_expense(expense_id: int) -> Tuple[Dict[str, str], int]:
    """
    Delete an expense.
    
    Args:
        expense_id: ID of expense to delete
    
    Returns:
        Tuple of (response_dict, status_code):
            200: Expense deleted successfully
            403: Expense belongs to different user
            404: Expense not found
    """
    expense = Expense.query.get_or_404(expense_id)
    
    if expense.user_id != request.current_user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    
    db.session.delete(expense)
    db.session.commit()
    
    return jsonify({'message': 'Expense deleted successfully'}), 200


@api_bp.route('/dashboard/stats', methods=['GET'])
@token_required
def dashboard_stats() -> Tuple[Dict[str, Any], int]:
    """
    Get dashboard statistics for authenticated user.
    
    Returns:
        Tuple of (response_dict, status_code):
            200: Dashboard statistics including today total, month total, budget, and warnings
    """
    # Note: These functions use Flask's current_user which won't work with JWT
    # So we need to set a temporary context
    from flask_login import current_user
    
    # For API endpoints with JWT, we calculate stats based on request.current_user_id
    today_expenses = Expense.query.filter(
        Expense.user_id == request.current_user_id,
        Expense.date == datetime.utcnow().date()
    ).all()
    today_total = sum(float(e.amount) for e in today_expenses)
    
    from datetime import date
    import calendar
    today = date.today()
    month_expenses = Expense.query.filter(
        Expense.user_id == request.current_user_id,
        Expense.date >= date(today.year, today.month, 1),
        Expense.date <= date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    ).all()
    month_total = sum(float(e.amount) for e in month_expenses)
    
    # Get budget from settings (simplified approach)
    from models import Setting
    budget_setting = Setting.query.filter_by(user_id=request.current_user_id, key='monthly_budget').first()
    budget = 0
    budget_warning = False
    
    if budget_setting:
        try:
            budget = float(budget_setting.value)
            if month_total > budget:
                budget_warning = True
        except ValueError:
            pass
    
    return jsonify({
        'today_total': round(today_total, 2),
        'month_total': round(month_total, 2),
        'budget': round(budget, 2),
        'budget_warning': budget_warning,
        'remaining_budget': round(budget - month_total, 2) if budget > 0 else 0
    }), 200

# ============================================================================
# ALERT ENDPOINTS - Budget Alerts & Notifications
# ============================================================================

@api_bp.route('/alerts', methods=['GET'])
@token_required
def get_user_alerts() -> Tuple[list, int]:
    """
    Get all alerts for authenticated user.
    
    Returns:
        Tuple of (response_list, status_code):
            200: List of alerts
    """
    alerts = Alert.query.filter_by(user_id=request.current_user_id).order_by(Alert.created_at.desc()).all()
    
    return jsonify([{
        'id': a.id,
        'alert_type': a.alert_type,
        'title': a.title,
        'message': a.message,
        'severity': a.severity,
        'is_read': a.is_read,
        'created_at': a.created_at.isoformat()
    } for a in alerts]), 200


@api_bp.route('/alerts/unread', methods=['GET'])
@token_required
def get_unread_alerts() -> Tuple[list, int]:
    """
    Get unread alerts for authenticated user.
    
    Returns:
        Tuple of (response_list, status_code):
            200: List of unread alerts only
    """
    alerts = Alert.query.filter_by(user_id=request.current_user_id, is_read=False).order_by(Alert.created_at.desc()).all()
    
    return jsonify({
        'count': len(alerts),
        'alerts': [{
            'id': a.id,
            'alert_type': a.alert_type,
            'title': a.title,
            'message': a.message,
            'severity': a.severity,
            'created_at': a.created_at.isoformat()
        } for a in alerts]
    }), 200


@api_bp.route('/alerts/<int:alert_id>/read', methods=['PUT'])
@token_required
def mark_alert_as_read(alert_id):
    """Mark an alert as read."""
    alert = Alert.query.get_or_404(alert_id)
    
    if alert.user_id != request.current_user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    
    alert.is_read = True
    db.session.commit()
    
    return jsonify({'message': 'Alert marked as read'}), 200


@api_bp.route('/alerts/<int:alert_id>', methods=['DELETE'])
@token_required
def delete_alert(alert_id):
    """Delete an alert."""
    alert = Alert.query.get_or_404(alert_id)
    
    if alert.user_id != request.current_user_id:
        return jsonify({'message': 'Unauthorized'}), 403
    
    db.session.delete(alert)
    db.session.commit()
    
    return jsonify({'message': 'Alert deleted'}), 200


@api_bp.route('/budget/check', methods=['GET'])
@token_required
def check_budget_status():
    """Check budget status and trigger alerts if needed."""
    alert = check_budget_and_create_alerts(request.current_user_id)
    
    budget_setting = Setting.query.filter_by(user_id=request.current_user_id, key='monthly_budget').first()
    budget = float(budget_setting.value) if budget_setting else 0
    month_total = calculate_month_total()
    
    return jsonify({
        'budget': round(budget, 2),
        'spent': round(month_total, 2),
        'remaining': round(budget - month_total, 2) if budget > 0 else 0,
        'percentage_used': round((month_total / budget * 100) if budget > 0 else 0, 2),
        'alert_created': alert is not None,
        'alert': {
            'type': alert.alert_type,
            'message': alert.message,
            'severity': alert.severity
        } if alert else None
    }), 200


# ============ ANALYTICS API ENDPOINTS ============

@api_bp.route('/analytics/trends', methods=['GET'])
@token_required
def api_trends():
    """Get monthly spending trends."""
    months = request.args.get('months', 12, type=int)
    trends = get_monthly_trends(request.current_user_id, min(months, 24))
    return jsonify(trends), 200


@api_bp.route('/analytics/categories', methods=['GET'])
@token_required
def api_categories():
    """Get category breakdown."""
    months = request.args.get('months', 1, type=int)
    breakdown, total = get_category_breakdown(request.current_user_id, min(months, 12))
    return jsonify({'breakdown': breakdown, 'total': round(total, 2)}), 200


@api_bp.route('/analytics/top-categories', methods=['GET'])
@token_required
def api_top_categories():
    """Get top spending categories."""
    limit = request.args.get('limit', 5, type=int)
    months = request.args.get('months', 1, type=int)
    top_cats = get_highest_spending_categories(request.current_user_id, min(limit, 10), min(months, 12))
    return jsonify(top_cats), 200


@api_bp.route('/analytics/daily', methods=['GET'])
@token_required
def api_daily():
    """Get daily spending breakdown."""
    month = request.args.get('month', None)
    daily = get_daily_breakdown(request.current_user_id, month)
    return jsonify(daily), 200


@api_bp.route('/analytics/stats', methods=['GET'])
@token_required
def api_stats():
    """Get spending statistics."""
    months = request.args.get('months', 1, type=int)
    stats = get_spending_statistics(request.current_user_id, min(months, 12))
    return jsonify({k: round(v, 2) for k, v in stats.items()}), 200


@api_bp.route('/analytics/comparison', methods=['GET'])
@token_required
def api_comparison():
    """Get month-over-month comparison."""
    comparison = get_month_comparison(request.current_user_id)
    return jsonify(comparison), 200


# ============ FILE UPLOAD API ENDPOINTS ============

@api_bp.route('/upload/receipt', methods=['POST'])
@token_required
def api_upload_receipt():
    """Upload receipt file for an expense."""
    expense_id = request.form.get('expense_id', type=int)
    
    if not expense_id:
        return jsonify({'error': 'Missing expense_id'}), 400
    
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != request.current_user_id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    
    filename, error = save_upload_file(file, request.current_user_id)
    
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


@api_bp.route('/upload/delete-receipt/<int:expense_id>', methods=['POST'])
@token_required
def api_delete_receipt(expense_id):
    """Delete receipt file from expense."""
    expense = Expense.query.get(expense_id)
    if not expense or expense.user_id != request.current_user_id:
        return jsonify({'error': 'Expense not found'}), 404
    
    if expense.receipt_path:
        delete_upload_file(expense.receipt_path)
        expense.receipt_path = None
        db.session.commit()
        return jsonify({'success': True}), 200
    
    return jsonify({'error': 'No receipt attached'}), 400


# ============ MODERN AI FEATURES API ROUTES ============

@api_bp.route('/chat', methods=['POST'])
@token_required
def api_chat():
    """
    Chat with expense data using natural language.
    
    Request JSON:
        query: str - Natural language question about expenses
    
    Returns:
        Chat response with intent and confidence score
    """
    from services.chat_service import ExpenseChatAssistant
    from analytics_service import get_spending_statistics
    
    data = request.get_json()
    if not data or not data.get('query'):
        return jsonify({'error': 'Missing query'}), 400
    
    try:
        # Get current expense data
        expense_stats = get_spending_statistics(request.current_user_id)
        
        # Get chat response
        response = ExpenseChatAssistant.chat(
            query=data['query'],
            expense_data=expense_stats
        )
        
        return jsonify(response), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/voice/capture', methods=['POST'])
@token_required
def api_voice_capture():
    """
    Capture expense from voice transcript.
    
    Request JSON:
        transcript: str - Voice-to-text transcript
    
    Returns:
        Structured expense data ready for creation
    """
    from services.trending_service import VoiceExpenseCapture
    
    data = request.get_json()
    if not data or not data.get('transcript'):
        return jsonify({'error': 'Missing transcript'}), 400
    
    try:
        result = VoiceExpenseCapture.process_voice_input(data['transcript'])
        
        if result['status'] == 'error':
            return jsonify(result), 400
        
        return jsonify(result), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/recurring/detect', methods=['GET'])
@token_required
def api_recurring_detect():
    """
    Detect recurring expenses from user's expense history.
    
    Returns:
        List of detected recurring patterns with confidence scores
    """
    from services.recurring_service import RecurringExpenseDetector
    
    try:
        # Get all expenses for user
        expenses = Expense.query.filter_by(user_id=request.current_user_id).all()
        
        # Convert to dict format for analysis
        expenses_data = [
            {
                'title': e.title,
                'amount': float(e.amount),
                'date': e.date.isoformat(),
                'category': e.category
            }
            for e in expenses
        ]
        
        # Detect patterns
        patterns = RecurringExpenseDetector.detect_patterns(expenses_data)
        
        # Get subscription opportunities
        opportunities = RecurringExpenseDetector.get_subscription_opportunities(patterns)
        
        return jsonify({
            'recurring_patterns': patterns,
            'subscription_opportunities': opportunities,
            'total_patterns': len(patterns),
            'total_opportunities': len(opportunities)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/trending/categories', methods=['GET'])
@token_required
def api_trending_categories():
    """
    Get trending expense categories over recent period.
    
    Query Parameters:
        days: int - Number of days to analyze (default: 7)
    
    Returns:
        List of trending categories with growth rates and trends
    """
    from services.trending_service import TrendingInsights
    
    try:
        days = request.args.get('days', 7, type=int)
        
        # Get expenses
        expenses = Expense.query.filter_by(user_id=request.current_user_id).all()
        expenses_data = [
            {
                'category': e.category,
                'amount': float(e.amount),
                'date': e.date.isoformat()
            }
            for e in expenses
        ]
        
        # Get trending
        trending = TrendingInsights.get_trending_categories(expenses_data, days)
        
        return jsonify({
            'trending_categories': trending,
            'period_days': days,
            'total_categories': len(trending)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/trending/pace', methods=['GET'])
@token_required
def api_spending_pace():
    """
    Get current spending pace analysis.
    
    Returns:
        Daily average, monthly projection, and pace forecast
    """
    from services.trending_service import TrendingInsights
    
    try:
        # Get expenses
        expenses = Expense.query.filter_by(user_id=request.current_user_id).all()
        expenses_data = [
            {
                'amount': float(e.amount),
                'date': e.date.isoformat()
            }
            for e in expenses
        ]
        
        # Get pace analysis
        pace = TrendingInsights.get_spending_pace(expenses_data)
        
        return jsonify(pace), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============ ADMIN API ROUTES ============

@api_bp.route('/admin/users')
@token_required
def api_admin_users():
    """Get all users for admin."""
    if not request.current_user.is_admin():
        return jsonify({'message': 'Admin access required'}), 403
    
    from sqlalchemy import func
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


@api_bp.route('/admin/stats')
@token_required
def api_admin_stats():
    """Get system-wide statistics."""
    if not request.current_user.is_admin():
        return jsonify({'message': 'Admin access required'}), 403
    
    from sqlalchemy import func
    
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


@api_bp.route('/admin/promote-admin/<int:user_id>', methods=['POST'])
@token_required
def api_promote_admin(user_id):
    """Promote user to admin."""
    if not request.current_user.is_admin():
        return jsonify({'message': 'Admin access required'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    user.role = 'admin'
    db.session.commit()
    
    return jsonify({'success': True}), 200


@api_bp.route('/admin/demote-admin/<int:user_id>', methods=['POST'])
@token_required
def api_demote_admin(user_id):
    """Demote admin to regular user."""
    if not request.current_user.is_admin():
        return jsonify({'message': 'Admin access required'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent demoting self
    if user.id == request.current_user_id:
        return jsonify({'error': 'Cannot demote yourself'}), 400
    
    user.role = 'user'
    db.session.commit()
    
    return jsonify({'success': True}), 200


@api_bp.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@token_required
def api_delete_user(user_id):
    """Delete a user and all their data."""
    if not request.current_user.is_admin():
        return jsonify({'message': 'Admin access required'}), 403
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    # Prevent deleting self
    if user.id == request.current_user_id:
        return jsonify({'error': 'Cannot delete yourself'}), 400
    
    username = user.username
    
    # Delete related data (cascade will handle it)
    db.session.delete(user)
    db.session.commit()
    
    return jsonify({'success': True}), 200