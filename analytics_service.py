"""Analytics service for generating financial insights and reports."""
from typing import Dict, Tuple, List, Optional, Any
from datetime import datetime, timedelta
from models import db, Expense
from sqlalchemy import func
import json


def get_monthly_trends(user_id: int, months: int = 12) -> Dict[str, float]:
    """
    Get monthly spending trends for the past N months.
    
    Args:
        user_id: User ID
        months: Number of months to retrieve (default 12)
    
    Returns:
        Dictionary mapping month strings (YYYY-MM) to spending amounts
    """
    today = datetime.now().date()
    trends = {}
    
    for i in range(months, 0, -1):
        # Calculate first and last day of month
        target_date = today - timedelta(days=today.day + (i-1) * 30)
        first_day = target_date.replace(day=1)
        
        if first_day.month == 12:
            last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = first_day.replace(month=first_day.month + 1, day=1) - timedelta(days=1)
        
        month_key = first_day.strftime("%Y-%m")
        
        total = db.session.query(func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.date >= first_day,
            Expense.date <= last_day
        ).scalar() or 0
        
        trends[month_key] = float(total)
    
    return trends


def get_category_breakdown(user_id: int, months: int = 1) -> Tuple[Dict[str, Dict[str, Any]], float]:
    """
    Get spending breakdown by category for the past N months.
    
    Args:
        user_id: User ID
        months: Number of months to analyze (default 1)
    
    Returns:
        Tuple of (breakdown_dict, total_spent):
            breakdown_dict maps category names to {'amount': float, 'count': int, 'percentage': float}
            total_spent: Total amount spent across all categories
    """
    today = datetime.now().date()
    first_day = today.replace(day=1) - timedelta(days=(months-1) * 30)
    
    categories = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total'),
        func.count(Expense.id).label('count')
    ).filter(
        Expense.user_id == user_id,
        Expense.date >= first_day
    ).group_by(Expense.category).all()
    
    breakdown = {}
    total_all = 0
    
    for cat, total, count in categories:
        breakdown[cat] = {
            'amount': float(total),
            'count': count,
            'percentage': 0
        }
        total_all += float(total)
    
    # Calculate percentages
    if total_all > 0:
        for cat in breakdown:
            breakdown[cat]['percentage'] = round((breakdown[cat]['amount'] / total_all) * 100, 1)
    
    return breakdown, float(total_all)


def get_highest_spending_categories(user_id: int, limit: int = 5, months: int = 1) -> List[Dict[str, Any]]:
    """
    Get top spending categories.
    
    Args:
        user_id: User ID
        limit: Maximum number of categories to return (default 5)
        months: Number of months to analyze (default 1)
    
    Returns:
        List of dicts with category name and spending data, sorted by amount (descending)
    """
    breakdown, total = get_category_breakdown(user_id, months)
    
    # Sort by amount and get top N
    sorted_cats = sorted(breakdown.items(), key=lambda x: x[1]['amount'], reverse=True)[:limit]
    
    return [{'category': cat, **data} for cat, data in sorted_cats]


def get_daily_breakdown(user_id: int, month: Optional[str] = None) -> Dict[str, float]:
    """
    Get daily spending breakdown for a specific month.
    
    Args:
        user_id: User ID
        month: Month string in format 'YYYY-MM' (default: current month)
    
    Returns:
        Dictionary mapping date strings (ISO format) to spending amounts
    """
    from utils import parse_month
    
    if month:
        first_day, last_day = parse_month(month)
    else:
        today = datetime.now().date()
        first_day = today.replace(day=1)
        if first_day.month == 12:
            last_day = first_day.replace(year=first_day.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            last_day = first_day.replace(month=first_day.month + 1, day=1) - timedelta(days=1)
    
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= first_day,
        Expense.date <= last_day
    ).order_by(Expense.date).all()
    
    daily = {}
    for exp in expenses:
        date_key = exp.date.isoformat()
        if date_key not in daily:
            daily[date_key] = 0
        daily[date_key] += exp.amount
    
    return daily


def get_spending_statistics(user_id: int, months: int = 1) -> Dict[str, float]:
    """
    Get comprehensive spending statistics.
    
    Args:
        user_id: User ID
        months: Number of months to analyze (default 1)
    
    Returns:
        Dictionary with:
            - total: Total amount spent
            - average: Average amount per transaction
            - highest: Highest single transaction
            - lowest: Lowest single transaction
            - count: Number of transactions
    """
    today = datetime.now().date()
    first_day = today.replace(day=1) - timedelta(days=(months-1) * 30)
    
    expenses = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= first_day
    ).all()
    
    if not expenses:
        return {
            'total': 0,
            'average': 0,
            'highest': 0,
            'lowest': 0,
            'count': 0
        }
    
    amounts = [e.amount for e in expenses]
    
    return {
        'total': float(sum(amounts)),
        'average': float(sum(amounts) / len(amounts)) if amounts else 0,
        'highest': float(max(amounts)),
        'lowest': float(min(amounts)),
        'count': len(amounts)
    }


def get_month_comparison(user_id: int) -> Dict[str, Any]:
    """
    Compare current month vs previous month spending.
    
    Args:
        user_id: User ID
    
    Returns:
        Dictionary with:
            - current: Current month total
            - previous: Previous month total
            - change_percent: Percentage change
            - change_amount: Absolute amount change
            - current_month: Current month name (e.g., "January 2024")
            - previous_month: Previous month name
    """
    today = datetime.now().date()
    
    # Current month
    current_first = today.replace(day=1)
    if current_first.month == 12:
        current_last = current_first.replace(year=current_first.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        current_last = current_first.replace(month=current_first.month + 1, day=1) - timedelta(days=1)
    
    current_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= current_first,
        Expense.date <= current_last
    ).scalar() or 0
    
    # Previous month
    prev_first = (current_first - timedelta(days=1)).replace(day=1)
    if prev_first.month == 12:
        prev_last = prev_first.replace(year=prev_first.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        prev_last = prev_first.replace(month=prev_first.month + 1, day=1) - timedelta(days=1)
    
    prev_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= prev_first,
        Expense.date <= prev_last
    ).scalar() or 0
    
    current_total = float(current_total)
    prev_total = float(prev_total)
    
    change = 0
    if prev_total > 0:
        change = round(((current_total - prev_total) / prev_total) * 100, 1)
    
    return {
        'current': current_total,
        'previous': prev_total,
        'change_percent': change,
        'change_amount': round(current_total - prev_total, 2),
        'current_month': current_first.strftime("%B %Y"),
        'previous_month': prev_first.strftime("%B %Y")
    }
