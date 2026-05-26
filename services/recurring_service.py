"""Recurring Expense Detection Service - AI-Powered Pattern Recognition.

Detects recurring expenses automatically using pattern matching.
Identifies subscriptions, monthly bills, regular purchases.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


class RecurringExpenseDetector:
    """Detects recurring expense patterns automatically."""
    
    @staticmethod
    def detect_patterns(expenses: list, min_occurrences: int = 2) -> list:
        """
        Detect recurring expense patterns.
        
        Args:
            expenses: List of expense dicts with 'title', 'amount', 'date'
            min_occurrences: Minimum repeats to consider recurring
            
        Returns:
            list of recurring patterns with confidence scores
        """
        if len(expenses) < min_occurrences:
            return []
        
        try:
            patterns = defaultdict(list)
            
            # Group by merchant/title
            for expense in expenses:
                title = expense.get('title', 'Unknown').lower().strip()
                patterns[title].append(expense)
            
            recurring = []
            
            for title, expenses_list in patterns.items():
                if len(expenses_list) >= min_occurrences:
                    # Check if amounts are similar (within 10%)
                    from decimal import Decimal
                    amounts = [float(Decimal(str(e.get('amount', 0)))) for e in expenses_list]
                    avg_amount = sum(amounts) / len(amounts)
                    variance = sum(abs(a - avg_amount) for a in amounts) / len(amounts)
                    consistency = 1 - (variance / avg_amount if avg_amount > 0 else 1)
                    
                    # Detect frequency
                    dates = sorted([
                        datetime.fromisoformat(e.get('date', datetime.now().isoformat()).split('T')[0])
                        for e in expenses_list
                    ])
                    
                    if len(dates) > 1:
                        intervals = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                        avg_interval = sum(intervals) / len(intervals)
                        
                        # Classify frequency
                        if avg_interval <= 7:
                            frequency = 'weekly'
                        elif avg_interval <= 15:
                            frequency = 'bi-weekly'
                        elif avg_interval <= 35:
                            frequency = 'monthly'
                        else:
                            frequency = 'irregular'
                        
                        confidence = min(consistency * (len(expenses_list) / 5), 1.0)
                        
                        recurring.append({
                            'merchant': title,
                            'amount': float(round(avg_amount, 2)),
                            'frequency': frequency,
                            'occurrences': len(expenses_list),
                            'consistency': float(round(consistency, 2)),
                            'confidence': float(round(confidence, 2)),
                            'avg_interval_days': int(round(avg_interval)),
                            'category': expenses_list[0].get('category', 'Other'),
                            'annual_cost': float(round(avg_amount * 12, 2))
                        })
            
            # Sort by confidence
            return sorted(recurring, key=lambda x: x['confidence'], reverse=True)
        
        except Exception as e:
            logger.error(f"Pattern detection error: {str(e)}")
            return []
    
    @staticmethod
    def get_subscription_opportunities(recurring_patterns: list) -> list:
        """
        Identify high-value subscriptions for budget tracking.
        
        Args:
            recurring_patterns: Output from detect_patterns()
            
        Returns:
            list of subscription insights
        """
        opportunities = []
        
        for pattern in recurring_patterns:
            if pattern['confidence'] > 0.7 and pattern['annual_cost'] > 50:
                opportunities.append({
                    'type': 'subscription',
                    'merchant': pattern['merchant'],
                    'monthly_cost': float(pattern['amount']),
                    'annual_cost': float(pattern['annual_cost']),
                    'frequency': pattern['frequency'],
                    'recommendation': f"This is a recurring expense. Consider tracking or cancelling if unused.",
                    'savings_potential': float(pattern['amount'] * 12)  # Potential annual savings
                })
        
        return sorted(opportunities, key=lambda x: x['annual_cost'], reverse=True)
