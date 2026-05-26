"""Utility functions for Expense Tracker application."""
from typing import Optional, Dict, Tuple, List
from datetime import date, datetime
from decimal import Decimal
import calendar
from flask_login import current_user
from models import Setting, Expense, Alert, db


def get_setting(key: str, user_id: Optional[int] = None) -> Optional[str]:
    """
    Retrieve a user setting by key.
    
    Args:
        key: Setting key name (e.g., 'monthly_budget', 'currency')
        user_id: User ID (defaults to current_user.id)
    
    Returns:
        Setting value as string, or None if not found
    """
    if user_id is None:
        user_id = current_user.id
    setting = Setting.query.filter_by(user_id=user_id, key=key).first()
    return setting.value if setting else None


def set_setting(key: str, value: str, user_id: Optional[int] = None) -> None:
    """
    Set or update a user setting.
    
    Creates new setting if key doesn't exist, updates existing otherwise.
    
    Args:
        key: Setting key name
        value: Setting value to store
        user_id: User ID (defaults to current_user.id)
    """
    if user_id is None:
        user_id = current_user.id
    setting = Setting.query.filter_by(user_id=user_id, key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(user_id=user_id, key=key, value=value)
        db.session.add(setting)
    db.session.commit()


def parse_month(month_str: str) -> Tuple[Optional[date], Optional[date]]:
    """
    Parse a month string in format 'YYYY-MM' and return first and last dates.
    
    Args:
        month_str: Month string (e.g., '2024-03')
    
    Returns:
        Tuple of (first_date, last_date) for the month, or (None, None) if invalid
    
    Example:
        >>> first, last = parse_month('2024-03')
        >>> first
        datetime.date(2024, 3, 1)
        >>> last
        datetime.date(2024, 3, 31)
    """
    try:
        year, month = map(int, month_str.split('-'))
        first = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        last = date(year, month, last_day)
        return first, last
    except (ValueError, AttributeError):
        return None, None


def calculate_today_total() -> float:
    """
    Calculate total expenses for today.
    
    Returns:
        Sum of all expenses for current user today
    """
    today = date.today()
    today_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date == today
    ).all()
    total = sum((e.amount for e in today_expenses), Decimal(0))
    return float(total)


def calculate_month_total(user_id: Optional[int] = None) -> float:
    """
    Calculate total expenses for current month.
    
    Args:
        user_id: User ID (defaults to current_user.id)
    
    Returns:
        Sum of all expenses for the user in current month
    """
    if user_id is None:
        user_id = current_user.id
    today = date.today()
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= date(today.year, today.month, 1),
        Expense.date <= date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    ).all()
    total = sum((e.amount for e in month_expenses), Decimal(0))
    return float(total)


def get_monthly_budget(user_id: Optional[int] = None) -> Tuple[float, bool]:
    """
    Get monthly budget and check if exceeded.
    
    Args:
        user_id: User ID (defaults to current_user.id)
    
    Returns:
        Tuple of (budget_amount, is_budget_exceeded)
    """
    budget_str = get_setting('monthly_budget', user_id) or ''
    budget: float = 0.0
    budget_warning: bool = False
    
    if budget_str:
        try:
            budget = float(budget_str)
            month_total = calculate_month_total(user_id)
            if month_total > budget:
                budget_warning = True
        except ValueError:
            budget = 0.0
    
    return budget, budget_warning


def calculate_category_spending(expenses: List[Expense]) -> Dict[str, Decimal]:
    """
    Calculate spending breakdown by category.
    
    Args:
        expenses: List of Expense objects
    
    Returns:
        Dictionary mapping category names to total amounts spent
    
    Example:
        >>> result = calculate_category_spending(expenses)
        >>> result['food']
        Decimal('150.50')
    """
    category_spending: Dict[str, Decimal] = {}
    for expense in expenses:
        if expense.category not in category_spending:
            category_spending[expense.category] = Decimal(0)
        category_spending[expense.category] += expense.amount
    
    return category_spending


def check_budget_and_create_alerts(user_id: int) -> Optional[Alert]:
    """
    Check if user's spending exceeds budget and create alerts.
    
    Creates alerts when spending exceeds 80% of budget (warning)
    or exceeds budget amount (danger). Only creates one alert per
    month per alert type.
    
    Args:
        user_id: User ID
    
    Returns:
        Created Alert object, or None if no alert was created
    """
    from datetime import datetime
    
    today = date.today()
    current_month: str = f"{today.year}-{today.month:02d}"
    
    # Get user's budget
    budget_setting = Setting.query.filter_by(user_id=user_id, key='monthly_budget').first()
    if not budget_setting:
        return None
    
    try:
        budget = float(budget_setting.value)
    except (ValueError, TypeError):
        return None
    
    # Calculate current month's total
    month_expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= date(today.year, today.month, 1),
        Expense.date <= date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    ).all()
    month_total: float = float(sum((e.amount for e in month_expenses), Decimal(0)))
    
    # Check for existing alert for this month
    existing_alert = Alert.query.filter_by(
        user_id=user_id,
        triggered_month=current_month,
        alert_type='budget_exceeded'
    ).first()
    
    if month_total > budget:
        # Budget exceeded
        if not existing_alert:
            exceeded_by: float = month_total - budget
            percentage: float = (month_total / budget - 1) * 100
            alert = Alert(
                user_id=user_id,
                alert_type='budget_exceeded',
                title='Budget Exceeded! 🚨',
                message=f'You\'ve spent ${month_total:.2f}, exceeding your ${budget:.2f} budget by ${exceeded_by:.2f} ({percentage:.1f}%)',
                severity='danger',
                triggered_month=current_month
            )
            db.session.add(alert)
            db.session.commit()
            return alert
    elif month_total > budget * 0.8:
        # Warning: approaching budget (80%)
        warning_alert = Alert.query.filter_by(
            user_id=user_id,
            triggered_month=current_month,
            alert_type='budget_warning'
        ).first()
        
        if not warning_alert:
            remaining: float = budget - month_total
            percentage_used: float = (month_total / budget) * 100
            alert = Alert(
                user_id=user_id,
                alert_type='budget_warning',
                title='Budget Warning ⚠️',
                message=f'You\'ve spent ${month_total:.2f} of your ${budget:.2f} budget ({percentage_used:.1f}%). Only ${remaining:.2f} remaining.',
                severity='warning',
                triggered_month=current_month
            )
            db.session.add(alert)
            db.session.commit()
            return alert
    
    return None


def get_active_alerts(user_id: int) -> List[Alert]:
    """
    Get unread alerts for a user.
    
    Args:
        user_id: User ID
    
    Returns:
        List of unread Alert objects for the user, ordered by creation date (newest first)
    """
    return Alert.query.filter_by(
        user_id=user_id,
        is_read=False
    ).order_by(Alert.created_at.desc()).all()


def get_month_comparison() -> Optional[Dict[str, any]]:
    """
    Compare current month spending with previous month.
    
    Calculates spending for current month and previous month,
    and determines percentage change and trend direction.
    
    Returns:
        Dictionary with:
            - current_month: float - Total spent this month
            - previous_month: float - Total spent previous month
            - percentage_change: float - Percentage change (positive = increase)
            - is_increase: bool - True if spending increased
        Returns None if previous month had no expenses (can't calculate percentage)
    """
    today = date.today()
    
    # Current month
    current_month_start = date(today.year, today.month, 1)
    current_month_end = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    current_month_total = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= current_month_start,
        Expense.date <= current_month_end
    ).with_entities(Expense.amount).all()
    current_total: float = sum(e[0] for e in current_month_total)
    
    # Previous month
    if today.month == 1:
        prev_month = 12
        prev_year = today.year - 1
    else:
        prev_month = today.month - 1
        prev_year = today.year
    
    prev_month_start = date(prev_year, prev_month, 1)
    prev_month_end = date(prev_year, prev_month, calendar.monthrange(prev_year, prev_month)[1])
    prev_month_total = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= prev_month_start,
        Expense.date <= prev_month_end
    ).with_entities(Expense.amount).all()
    prev_total: float = sum(e[0] for e in prev_month_total)
    
    if prev_total == 0:
        return None
    
    percentage_change: float = ((current_total - prev_total) / prev_total) * 100
    return {
        'current_month': current_total,
        'previous_month': prev_total,
        'percentage_change': percentage_change,
        'is_increase': percentage_change > 0
    }
