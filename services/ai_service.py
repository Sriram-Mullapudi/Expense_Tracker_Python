"""AI-Powered Expense Intelligence Service.

Provides machine learning features:
- Anomaly detection for unusual spending patterns
- Spending forecasting with ARIMA
- Smart categorization with ML classifier
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from decimal import Decimal
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from statsmodels.tsa.arima.model import ARIMA
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """Detects unusual spending patterns using Isolation Forest."""
    
    @staticmethod
    def detect_anomalies(expenses: list, contamination: float = 0.1) -> dict:
        """
        Detect anomalous expenses using Isolation Forest.
        
        Args:
            expenses: List of expense dictionaries with 'amount' and 'date' keys
            contamination: Expected proportion of anomalies (0.0-1.0)
            
        Returns:
            dict with 'anomalies' list and 'threshold' float
        """
        if len(expenses) < 5:
            return {'anomalies': [], 'threshold': None, 'status': 'insufficient_data'}
        
        try:
            # Prepare data
            amounts = np.array([float(e.get('amount', 0)) for e in expenses]).reshape(-1, 1)
            
            # Standardize
            scaler = StandardScaler()
            amounts_scaled = scaler.fit_transform(amounts)
            
            # Fit Isolation Forest
            iso_forest = IsolationForest(contamination=contamination, random_state=42)
            predictions = iso_forest.fit_predict(amounts_scaled)
            
            # Identify anomalies (-1 = anomaly, 1 = normal)
            anomaly_indices = np.where(predictions == -1)[0]
            anomalies = [expenses[i] for i in anomaly_indices]
            
            # Calculate threshold (upper 90th percentile)
            threshold = float(np.percentile(amounts, 90))
            
            return {
                'anomalies': anomalies,
                'threshold': threshold,
                'count': len(anomalies),
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"Anomaly detection error: {str(e)}")
            return {'anomalies': [], 'threshold': None, 'status': 'error', 'error': str(e)}


class SpendingForecaster:
    """Predicts future spending using ARIMA time-series model."""
    
    @staticmethod
    def forecast_next_month(monthly_totals: dict, periods: int = 30) -> dict:
        """
        Forecast spending for next period using ARIMA.
        
        Args:
            monthly_totals: Dict with month keys and spending values
            periods: Number of days to forecast (default 30)
            
        Returns:
            dict with forecast values and confidence intervals
        """
        if len(monthly_totals) < 3:
            return {'forecast': None, 'status': 'insufficient_data'}
        
        try:
            # Prepare time series
            values = list(monthly_totals.values())
            
            # Fit ARIMA model (1,1,1) - common for financial data
            model = ARIMA(values, order=(1, 1, 1))
            fitted_model = model.fit()
            
            # Forecast
            forecast_result = fitted_model.get_forecast(steps=1)
            forecast_value = float(forecast_result.predicted_mean.iloc[0])
            conf_int = forecast_result.conf_int().iloc[0]
            
            return {
                'forecast': forecast_value,
                'lower_bound': float(conf_int[0]),
                'upper_bound': float(conf_int[1]),
                'confidence': 0.95,
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"Forecasting error: {str(e)}")
            return {'forecast': None, 'status': 'error', 'error': str(e)}


class SmartCategorizer:
    """AI-powered expense categorization based on descriptions."""
    
    # ML-based category mapping (rule-based for MVP)
    CATEGORY_KEYWORDS = {
        'Food': ['restaurant', 'cafe', 'grocery', 'pizza', 'burger', 'food', 'lunch', 'dinner', 'breakfast', 'coffee'],
        'Transport': ['uber', 'taxi', 'gas', 'parking', 'transit', 'bus', 'train', 'fuel', 'metro', 'transport'],
        'Entertainment': ['movie', 'cinema', 'game', 'concert', 'spotify', 'netflix', 'entertainment', 'show', 'ticket'],
        'Shopping': ['amazon', 'walmart', 'target', 'mall', 'store', 'shopping', 'retail', 'buy', 'shop'],
        'Utilities': ['electricity', 'water', 'gas', 'phone', 'internet', 'utility', 'bill', 'rent'],
        'Health': ['pharmacy', 'doctor', 'hospital', 'medicine', 'health', 'dental', 'clinic', 'medical'],
        'Other': []
    }
    
    @staticmethod
    def categorize(description: str, amount: float = None) -> dict:
        """
        Intelligently categorize expense based on description.
        
        Args:
            description: Expense description/merchant name
            amount: Optional amount for context
            
        Returns:
            dict with 'category' and 'confidence' score
        """
        if not description:
            return {'category': 'Other', 'confidence': 0.0}
        
        try:
            description_lower = description.lower()
            scores = {}
            
            # Score each category
            for category, keywords in SmartCategorizer.CATEGORY_KEYWORDS.items():
                matches = sum(1 for keyword in keywords if keyword in description_lower)
                scores[category] = matches
            
            # Get category with highest score
            best_category = max(scores, key=scores.get) if max(scores.values()) > 0 else 'Other'
            confidence = min(max(scores.values()) / len(description_lower.split()), 1.0)
            
            return {
                'category': best_category,
                'confidence': float(confidence),
                'status': 'success'
            }
        except Exception as e:
            logger.error(f"Categorization error: {str(e)}")
            return {'category': 'Other', 'confidence': 0.0, 'status': 'error', 'error': str(e)}


class InsightGenerator:
    """Generates intelligent insights about spending patterns."""
    
    @staticmethod
    def generate_insights(expenses: list, budget: float = None) -> list:
        """
        Generate actionable spending insights.
        
        Args:
            expenses: List of expenses with amounts and categories
            budget: Optional monthly budget
            
        Returns:
            list of insight dictionaries
        """
        insights = []
        
        if not expenses:
            return []
        
        try:
            total_spent = sum(float(e.get('amount', 0)) for e in expenses)
            
            # Insight 1: Budget warning
            if budget and total_spent > budget * 0.8:
                insights.append({
                    'type': 'budget_warning',
                    'severity': 'high' if total_spent > budget else 'medium',
                    'message': f'You have spent ${total_spent:.2f} of your ${budget:.2f} budget ({(total_spent/budget*100):.1f}%)',
                    'actionable': True
                })
            
            # Insight 2: Category analysis
            category_totals = {}
            for expense in expenses:
                cat = expense.get('category', 'Other')
                amt = float(expense.get('amount', 0))
                category_totals[cat] = category_totals.get(cat, 0) + amt
            
            if category_totals:
                top_category = max(category_totals, key=category_totals.get)
                top_amount = category_totals[top_category]
                percentage = (top_amount / total_spent * 100) if total_spent > 0 else 0
                
                if percentage > 40:
                    insights.append({
                        'type': 'high_category_spending',
                        'category': top_category,
                        'amount': float(top_amount),
                        'percentage': float(percentage),
                        'message': f'{top_category} is your highest expense ({percentage:.1f}% of total)',
                        'actionable': True
                    })
            
            # Insight 3: Spending trend
            if len(expenses) > 1:
                daily_amounts = [float(e.get('amount', 0)) for e in expenses]
                daily_avg = sum(daily_amounts) / len(daily_amounts)
                today_avg = daily_amounts[-1] if daily_amounts else 0
                
                if today_avg > daily_avg * 1.5:
                    insights.append({
                        'type': 'high_daily_spending',
                        'today_amount': float(today_avg),
                        'average': float(daily_avg),
                        'message': f'Today you spent ${today_avg:.2f}, which is {(today_avg/daily_avg*100):.1f}% above your daily average',
                        'actionable': True
                    })
            
            return insights
            
        except Exception as e:
            logger.error(f"Insight generation error: {str(e)}")
            return []
