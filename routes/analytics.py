"""Analytics routes for expense insights."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from analytics_service import (
    get_monthly_trends, get_category_breakdown, get_spending_statistics,
    get_month_comparison, get_daily_breakdown, get_highest_spending_categories
)
from insights_service import (
    generate_ai_insights, get_quick_stats, get_week_over_week_comparison,
    get_spending_anomalies, get_category_insights, get_spending_forecast
)

analytics_bp = Blueprint('analytics', __name__, url_prefix='/analytics')


@analytics_bp.route('/')
@login_required
def index():
    """Display analytics dashboard."""
    months = request.args.get('months', 6, type=int)
    months = min(max(months, 1), 12)  # Clamp between 1 and 12
    
    monthly_trends = get_monthly_trends(current_user.id, months)
    category_breakdown = get_category_breakdown(current_user.id)
    daily_breakdown = get_daily_breakdown(current_user.id)
    stats = get_spending_statistics(current_user.id, months)
    top_categories = get_highest_spending_categories(current_user.id, limit=5)
    
    return render_template(
        'analytics.html',
        monthly_trends=monthly_trends,
        category_breakdown=category_breakdown,
        daily_breakdown=daily_breakdown,
        stats=stats,
        top_categories=top_categories,
        months=months
    )


@analytics_bp.route('/api/trends')
@login_required
def api_trends():
    """Get monthly spending trends."""
    months = request.args.get('months', 6, type=int)
    months = min(max(months, 1), 12)
    data = get_monthly_trends(current_user.id, months)
    return jsonify(data)


@analytics_bp.route('/api/categories')
@login_required
def api_categories():
    """Get category breakdown."""
    data = get_category_breakdown(current_user.id)
    return jsonify(data)


@analytics_bp.route('/api/daily')
@login_required
def api_daily():
    """Get daily breakdown."""
    data = get_daily_breakdown(current_user.id)
    return jsonify(data)


@analytics_bp.route('/api/stats')
@login_required
def api_stats():
    """Get spending statistics."""
    months = request.args.get('months', 1, type=int)
    stats = get_spending_statistics(current_user.id, min(months, 12))
    return jsonify({k: round(v, 2) for k, v in stats.items()})


@analytics_bp.route('/api/comparison')
@login_required
def api_comparison():
    """Get month-over-month comparison."""
    comparison = get_month_comparison(current_user.id)
    return jsonify(comparison)


# ============ AI INSIGHTS ENDPOINTS ============

@analytics_bp.route('/insights')
@login_required
def insights():
    """Display AI insights dashboard."""
    ai_insights = generate_ai_insights(current_user.id)
    quick_stats = get_quick_stats(current_user.id)
    category_data = get_category_insights(current_user.id)
    forecast = get_spending_forecast(current_user.id)
    
    return render_template(
        'insights.html',
        insights=ai_insights,
        stats=quick_stats,
        categories=category_data,
        forecast=forecast
    )


@analytics_bp.route('/api/insights')
@login_required
def api_insights():
    """Get AI-powered insights."""
    insights = generate_ai_insights(current_user.id)
    return jsonify(insights)


@analytics_bp.route('/api/insights/quick-stats')
@login_required
def api_quick_stats():
    """Get quick statistics."""
    stats = get_quick_stats(current_user.id)
    return jsonify(stats)


@analytics_bp.route('/api/insights/week-comparison')
@login_required
def api_week_comparison():
    """Get week-over-week comparison."""
    data = get_week_over_week_comparison(current_user.id)
    return jsonify(data)


@analytics_bp.route('/api/insights/anomalies')
@login_required
def api_anomalies():
    """Get spending anomalies."""
    anomalies = get_spending_anomalies(current_user.id)
    return jsonify(anomalies)


@analytics_bp.route('/api/insights/categories')
@login_required
def api_categories_insights():
    """Get category insights."""
    data = get_category_insights(current_user.id)
    return jsonify(data)


@analytics_bp.route('/api/insights/forecast')
@login_required
def api_forecast():
    """Get spending forecast."""
    forecast = get_spending_forecast(current_user.id)
    return jsonify(forecast)

