"""AI Chat Assistant Service - Conversational Expense Intelligence.

Enables natural language queries about expenses, budgets, and insights.
Example: "How much did I spend on food last week?" "Show me my highest expense category"
"""

from datetime import datetime, timedelta
from decimal import Decimal
import re
import logging

logger = logging.getLogger(__name__)


class ExpenseChatAssistant:
    """Natural language interface for expense queries."""
    
    # Intents and patterns
    INTENTS = {
        'total_spending': {
            'patterns': [r'how much.*spend', r'total.*spent', r'.*spending.*total', r'what.*spent'],
            'response': 'total'
        },
        'category_spending': {
            'patterns': [r'.*spend.*on\s+(\w+)', r'.*in\s+(\w+)', r'.*category.*(\w+)'],
            'response': 'category'
        },
        'budget_status': {
            'patterns': [r'budget.*left', r'how much.*budget', r'remaining.*budget', r'budget.*remain'],
            'response': 'budget'
        },
        'time_period': {
            'patterns': [r'today', r'this week', r'this month', r'last.*week', r'last.*month'],
            'response': 'timeframe'
        },
        'highest_expense': {
            'patterns': [r'highest.*expense', r'most.*spent', r'biggest.*expense', r'max.*expense'],
            'response': 'highest'
        },
        'suggestions': {
            'patterns': [r'suggest', r'advice', r'recommend', r'help.*save', r'tips'],
            'response': 'suggestions'
        }
    }
    
    @staticmethod
    def parse_query(query: str) -> dict:
        """
        Parse natural language query into structured format.
        
        Args:
            query: Natural language question about expenses
            
        Returns:
            dict with 'intent' and 'parameters'
        """
        if not query:
            return {'intent': None, 'parameters': {}}
        
        query_lower = query.lower().strip()
        matched_intent = None
        parameters = {}
        
        # Match intent
        for intent_name, intent_data in ExpenseChatAssistant.INTENTS.items():
            for pattern in intent_data['patterns']:
                if re.search(pattern, query_lower):
                    matched_intent = intent_name
                    break
        
        # Extract parameters
        if 'spend' in query_lower and 'on' in query_lower:
            match = re.search(r'on\s+(\w+)', query_lower)
            if match:
                parameters['category'] = match.group(1)
        
        # Time period extraction
        if 'today' in query_lower:
            parameters['period'] = 'today'
        elif 'week' in query_lower:
            parameters['period'] = 'week'
        elif 'month' in query_lower:
            parameters['period'] = 'month'
        
        return {
            'intent': matched_intent or 'general',
            'parameters': parameters,
            'original_query': query
        }
    
    @staticmethod
    def generate_response(parsed_query: dict, expense_data: dict) -> str:
        """
        Generate natural language response based on query and data.
        
        Args:
            parsed_query: Output from parse_query()
            expense_data: Expense statistics
            
        Returns:
            str - Natural language response
        """
        intent = parsed_query.get('intent')
        params = parsed_query.get('parameters', {})
        
        try:
            if intent == 'total_spending':
                total = float(expense_data.get('total_spent', 0))
                period = params.get('period', 'this month')
                return f"You've spent ${total:.2f} {period}."
            
            elif intent == 'category_spending':
                category = params.get('category', 'that category')
                breakdown = expense_data.get('breakdown', {})
                amount = float(breakdown.get(category.title(), {}).get('amount', 0))
                return f"You spent ${amount:.2f} on {category}."
            
            elif intent == 'budget_status':
                remaining = float(expense_data.get('remaining_budget', 0))
                percent = float(expense_data.get('budget_used_percent', 0))
                if remaining > 0:
                    return f"You have ${remaining:.2f} left in your budget ({percent:.1f}% used)."
                else:
                    return f"You've exceeded your budget by ${abs(remaining):.2f}."
            
            elif intent == 'highest_expense':
                top_category = expense_data.get('top_category')
                top_amount = float(expense_data.get('top_amount', 0))
                return f"Your highest spending is on {top_category}: ${top_amount:.2f}."
            
            elif intent == 'suggestions':
                suggestions = expense_data.get('suggestions', [])
                if suggestions:
                    return f"Here's my suggestion: {suggestions[0]}"
                return "Keep tracking your expenses to get personalized suggestions!"
            
            else:
                return "I can help with questions about your spending. Try asking about your total spending, budget, or categories."
        
        except Exception as e:
            logger.error(f"Chat response generation error: {str(e)}")
            return "I'm having trouble understanding that. Can you rephrase?"
    
    @staticmethod
    def chat(query: str, expense_data: dict) -> dict:
        """
        Main chat interface.
        
        Args:
            query: User's natural language question
            expense_data: Current expense statistics
            
        Returns:
            dict with 'response', 'intent', 'confidence'
        """
        parsed = ExpenseChatAssistant.parse_query(query)
        response = ExpenseChatAssistant.generate_response(parsed, expense_data)
        
        return {
            'query': query,
            'response': response,
            'intent': parsed['intent'],
            'confidence': 0.85 if parsed['intent'] else 0.3,
            'timestamp': datetime.now().isoformat()
        }
