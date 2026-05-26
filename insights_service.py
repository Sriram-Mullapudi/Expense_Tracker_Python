"""AI-powered expense insights engine."""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy import func
from models import db, Expense
from utils import parse_month


def get_week_over_week_comparison(user_id: int) -> Dict[str, Any]:
    """
    Compare this week vs last week spending.
    
    Args:
        user_id: User ID
    
    Returns:
        Dictionary with:
            - this_week: float - This week's total
            - last_week: float - Last week's total
            - percent_change: float - Percentage change
            - direction: str - 'up', 'down', or 'same'
            - amount_diff: float - Absolute difference
    """
    today = datetime.now().date()
    
    # This week (Mon-Sun)
    days_since_monday = today.weekday()
    this_week_start = today - timedelta(days=days_since_monday)
    this_week_end = this_week_start + timedelta(days=6)
    
    # Last week
    last_week_start = this_week_start - timedelta(days=7)
    last_week_end = this_week_start - timedelta(days=1)
    
    this_week_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= this_week_start,
        Expense.date <= this_week_end
    ).scalar() or 0
    
    last_week_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= last_week_start,
        Expense.date <= last_week_end
    ).scalar() or 0
    
    if last_week_total == 0:
        percent_change = 0
    else:
        percent_change = ((this_week_total - last_week_total) / last_week_total) * 100
    
    return {
        'this_week': round(this_week_total, 2),
        'last_week': round(last_week_total, 2),
        'percent_change': round(percent_change, 1),
        'direction': 'up' if percent_change > 0 else 'down' if percent_change < 0 else 'same',
        'amount_diff': round(abs(this_week_total - last_week_total), 2)
    }


def get_spending_anomalies(user_id: int) -> List[Dict[str, Any]]:
    """
    Detect unusual spending patterns.
    
    Identifies expenses significantly higher than average (>2x) in past 30 days.
    
    Args:
        user_id: User ID
    
    Returns:
        List of dicts with anomaly details, sorted by amount (descending)
    """
    today = datetime.now().date()
    this_month_start = today.replace(day=1)
    
    # Get last 30 days of data
    thirty_days_ago = today - timedelta(days=30)
    expenses_30d = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= thirty_days_ago,
        Expense.date <= today
    ).all()
    
    if len(expenses_30d) == 0:
        return []
    
    # Calculate average daily spending (convert Decimal to float for calculations)
    days_with_spending = len(set(e.date for e in expenses_30d))
    total_spending = sum((e.amount for e in expenses_30d), Decimal(0))
    avg_daily = float(total_spending) / max(days_with_spending, 1)
    
    # Find anomalies (expenses > 2x average)
    anomalies = []
    for expense in expenses_30d:
        if expense.amount > avg_daily * 2:
            anomalies.append({
                'date': expense.date.isoformat(),
                'title': expense.title,
                'category': expense.category,
                'amount': round(expense.amount, 2),
                'vs_average': round((expense.amount / avg_daily), 1),
                'severity': 'high' if expense.amount > avg_daily * 3 else 'medium'
            })
    
    return sorted(anomalies, key=lambda x: x['amount'], reverse=True)[:5]


def get_category_insights(user_id: int) -> Dict[str, Dict[str, Any]]:
    """
    Get insights about top spending categories.
    
    Args:
        user_id: User ID
    
    Returns:
        Dict mapping category names to {'amount': float, 'percentage': float, 'rank': int}
    """
    today = datetime.now().date()
    this_month_start = today.replace(day=1)
    
    # This month spending by category
    category_spending = db.session.query(
        Expense.category,
        func.sum(Expense.amount).label('total')
    ).filter(
        Expense.user_id == user_id,
        Expense.date >= this_month_start,
        Expense.date <= today
    ).group_by(Expense.category).order_by(func.sum(Expense.amount).desc()).all()
    
    if not category_spending:
        return {}
    
    total_spending = sum(cat[1] for cat in category_spending)
    
    insights = {}
    for i, (category, amount) in enumerate(category_spending):
        percentage = (amount / total_spending * 100) if total_spending > 0 else 0
        insights[category] = {
            'amount': round(amount, 2),
            'percentage': round(percentage, 1),
            'rank': i + 1
        }
    
    return insights


def get_spending_forecast(user_id: int) -> Dict[str, Any]:
    """
    Forecast spending based on current pace.
    
    Projects end-of-month spending based on current daily average.
    
    Args:
        user_id: User ID
    
    Returns:
        Dict with:
            - spent_so_far: float - Amount spent this month so far
            - projected_total: float - Projected end-of-month total
            - days_into_month: int - Current day of month
            - days_in_month: int - Total days in month
            - daily_average: float - Average daily spending
    """
    today = datetime.now().date()
    this_month_start = today.replace(day=1)
    
    # Get spending so far this month
    month_spent = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= this_month_start,
        Expense.date <= today
    ).scalar() or 0
    
    # Days into month
    days_into_month = (today - this_month_start).days + 1
    days_in_month = (this_month_start.replace(month=this_month_start.month % 12 + 1, day=1) - timedelta(days=1)).day
    
    # Project to end of month
    if days_into_month > 0:
        daily_average = month_spent / days_into_month
        projected_total = daily_average * days_in_month
    else:
        projected_total = 0
    
    return {
        'spent_so_far': round(month_spent, 2),
        'projected_total': round(projected_total, 2),
        'days_into_month': days_into_month,
        'days_in_month': days_in_month,
        'daily_average': round(month_spent / days_into_month, 2) if days_into_month > 0 else 0
    }


def generate_ai_insights(user_id: int) -> List[str]:
    """
    Generate human-readable AI insights about user spending patterns.
    
    Args:
        user_id: User ID
    
    Returns:
        List of insight strings
    """
    insights = []
    
    # Week-over-week insight
    wow = get_week_over_week_comparison(user_id)
    if wow['last_week'] > 0:
        if wow['percent_change'] > 10:
            insights.append({
                'type': 'warning',
                'emoji': '📈',
                'title': 'Spending Up This Week',
                'message': f"You spent {wow['percent_change']}% more this week (${wow['amount_diff']:.2f}) compared to last week.",
                'action': 'Review your expenses and adjust if needed'
            })
        elif wow['percent_change'] < -10:
            insights.append({
                'type': 'success',
                'emoji': '📉',
                'title': 'Great Job! Spending Down',
                'message': f"You spent {abs(wow['percent_change'])}% less this week - that's ${wow['amount_diff']:.2f} saved!",
                'action': 'Keep up the good spending habits!'
            })
    
    # Anomaly detection
    anomalies = get_spending_anomalies(user_id)
    if anomalies:
        highest = anomalies[0]
        insights.append({
            'type': 'info',
            'emoji': '🔍',
            'title': 'Large Expense Detected',
            'message': f"${highest['amount']:.2f} spent on {highest['title']} ({highest['category']}) - about {highest['vs_average']}x your daily average.",
            'action': 'Was this expected?'
        })
    
    # Category insight
    category_data = get_category_insights(user_id)
    if category_data:
        top_category = max(category_data.items(), key=lambda x: x[1]['percentage'])
        insights.append({
            'type': 'info',
            'emoji': '💰',
            'title': f"Top Spending: {top_category[0]}",
            'message': f"{top_category[1]['percentage']}% of your spending is on {top_category[0]} (${top_category[1]['amount']:.2f}).",
            'action': 'Is this higher than you expected?'
        })
    
    # Spending forecast
    forecast = get_spending_forecast(user_id)
    if forecast['days_into_month'] > 0:
        insights.append({
            'type': 'forecast',
            'emoji': '📊',
            'title': 'Month-End Projection',
            'message': f"At your current pace, you'll spend ~${forecast['projected_total']:.2f} this month (${forecast['daily_average']:.2f}/day).",
            'action': 'Plan accordingly'
        })
    
    return insights


def get_quick_stats(user_id):
    """Get quick statistics for dashboard."""
    today = datetime.now().date()
    this_month_start = today.replace(day=1)
    
    # Today
    today_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date == today
    ).scalar() or 0
    
    # This month
    month_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= this_month_start,
        Expense.date <= today
    ).scalar() or 0
    
    # This year
    year_start = today.replace(month=1, day=1)
    year_total = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= year_start,
        Expense.date <= today
    ).scalar() or 0
    
    # Average daily (last 30 days)
    thirty_days_ago = today - timedelta(days=30)
    last_30_days = db.session.query(func.sum(Expense.amount)).filter(
        Expense.user_id == user_id,
        Expense.date >= thirty_days_ago,
        Expense.date <= today
    ).scalar() or 0
    daily_avg = last_30_days / 30
    
    # Count transactions
    expense_count = Expense.query.filter(
        Expense.user_id == user_id,
        Expense.date >= this_month_start,
        Expense.date <= today
    ).count()
    
    return {
        'today': round(today_total, 2),
        'this_month': round(month_total, 2),
        'this_year': round(year_total, 2),
        'daily_average': round(daily_avg, 2),
        'expense_count': expense_count
    }
