"""Voice & Trending Insights Service - Modern Real-time Features.

Voice expense capture and trending spending patterns.
"""

import logging
from datetime import datetime, timedelta
from collections import Counter

logger = logging.getLogger(__name__)


class VoiceExpenseCapture:
    """Process voice input for expense creation."""
    
    EXPENSE_PATTERNS = {
        'spent': True,
        'paid': True,
        'charged': True,
        'cost': True,
        'bought': True,
        'purchase': True,
    }
    
    @staticmethod
    def process_voice_input(transcript: str) -> dict:
        """
        Convert voice transcript to structured expense.
        
        Example: "I spent 25 dollars on coffee" 
        -> {amount: 25, category: 'Food', description: 'coffee'}
        
        Args:
            transcript: Voice-to-text transcript
            
        Returns:
            dict with structured expense data or error
        """
        if not transcript:
            return {'status': 'error', 'message': 'No input provided'}
        
        try:
            # Extract amount (looks for numbers with dollar signs or 'dollars')
            import re
            amount_match = re.search(r'(\d+(?:\.\d{2})?)\s*(?:dollars?|bucks?|\$)?', transcript.lower())
            
            if not amount_match:
                return {'status': 'error', 'message': 'Could not find amount in transcript'}
            
            amount = float(amount_match.group(1))
            
            # Extract category keywords
            categories = {
                'food': ['coffee', 'lunch', 'dinner', 'restaurant', 'food', 'eat', 'pizza'],
                'transport': ['uber', 'taxi', 'gas', 'parking', 'transit'],
                'shopping': ['store', 'buy', 'mall', 'amazon'],
                'entertainment': ['movie', 'concert', 'ticket'],
                'health': ['doctor', 'medicine', 'pharmacy'],
            }
            
            detected_category = 'Other'
            for category, keywords in categories.items():
                if any(keyword in transcript.lower() for keyword in keywords):
                    detected_category = category.title()
                    break
            
            # Extract description
            description = transcript.replace('dollars', '').replace('bucks', '').strip()
            description = description[:100]  # Limit to 100 chars
            
            return {
                'status': 'success',
                'amount': float(amount),
                'category': detected_category,
                'description': description,
                'date': datetime.now().isoformat(),
                'confidence': 0.95
            }
        
        except Exception as e:
            logger.error(f"Voice processing error: {str(e)}")
            return {'status': 'error', 'message': str(e)}


class TrendingInsights:
    """Real-time trending analysis of spending patterns."""
    
    @staticmethod
    def get_trending_categories(expenses: list, days: int = 7) -> list:
        """
        Get trending expense categories over recent period.
        
        Args:
            expenses: List of expenses
            days: Number of days to analyze
            
        Returns:
            list of trending categories with growth rates
        """
        if not expenses:
            return []
        
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            recent_expenses = [
                e for e in expenses 
                if datetime.fromisoformat(e.get('date', '2000-01-01').split('T')[0]) > cutoff_date.date()
            ]
            
            if len(recent_expenses) < 2:
                return []
            
            # Count categories
            category_counts = Counter(e.get('category', 'Other') for e in recent_expenses)
            
            from decimal import Decimal
            trending = []
            for category, count in category_counts.most_common(5):
                amount = sum(float(Decimal(str(e.get('amount', 0)))) for e in recent_expenses 
                           if e.get('category') == category)
                
                trending.append({
                    'category': category,
                    'count': count,
                    'total_amount': float(round(amount, 2)),
                    'avg_per_transaction': float(round(amount / count, 2)),
                    'trend': 'up',  # Can be enhanced with ML
                    'rank': len(trending) + 1
                })
            
            return trending
        
        except Exception as e:
            logger.error(f"Trending analysis error: {str(e)}")
            return []
    
    @staticmethod
    def get_spending_pace(expenses: list) -> dict:
        """
        Analyze current spending pace vs daily average.
        
        Returns:
            dict with pace analysis and projections
        """
        if not expenses:
            return {'status': 'insufficient_data'}
        
        try:
            from decimal import Decimal
            today = datetime.now().date()
            this_month_start = today.replace(day=1)
            
            # Calculate daily average historically
            all_amounts = [float(Decimal(str(e.get('amount', 0)))) for e in expenses]
            daily_avg = sum(all_amounts) / len(all_amounts) if all_amounts else 0
            
            # Calculate this month's pace
            this_month_expenses = [
                e for e in expenses
                if datetime.fromisoformat(e.get('date', '2000-01-01').split('T')[0]).date() >= this_month_start
            ]
            
            this_month_total = sum(float(Decimal(str(e.get('amount', 0)))) for e in this_month_expenses)
            days_in_month = (today.replace(month=today.month % 12 + 1, day=1) - timedelta(days=1)).day
            days_elapsed = (today - this_month_start).days + 1
            
            monthly_projection = (this_month_total / days_elapsed) * days_in_month if days_elapsed > 0 else 0
            
            return {
                'status': 'success',
                'daily_average': float(round(daily_avg, 2)),
                'this_month_total': float(round(this_month_total, 2)),
                'projected_monthly': float(round(monthly_projection, 2)),
                'days_elapsed': days_elapsed,
                'pace': 'fast' if monthly_projection > daily_avg * 30 * 1.1 else 'normal' if monthly_projection > daily_avg * 30 * 0.9 else 'slow',
                'forecast_status': 'on_track' if daily_avg * 30 > 0 and abs(monthly_projection - daily_avg * 30) / (daily_avg * 30) < 0.1 else 'warning'
            }
        
        except Exception as e:
            logger.error(f"Spending pace error: {str(e)}")
            return {'status': 'error', 'message': str(e)}
