"""BudgetService - Pure Python business logic for budget operations.

This module provides budget management operations without any Flask dependencies.
All methods return clean dictionaries with success/error information.
Can be used from web routes, REST APIs, CLI tools, or background jobs.

Methods:
    set_budget() - Set monthly budget for user
    get_budget() - Get current budget and spending status
    check_budget_exceeds() - Check if spending exceeds budget
    get_budget_status() - Get detailed budget status with percentage
    reset_monthly_alerts() - Clear monthly alerts
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any

from models import db, User, Expense, Setting, Alert


class BudgetService:
    """Budget management service - pure Python, no Flask imports."""
    
    @staticmethod
    def set_budget(user_id: int, budget_amount: float) -> Dict[str, Any]:
        """
        Set the monthly budget for a user.
        
        Args:
            user_id: User ID
            budget_amount: Monthly budget in dollars (must be > 0)
        
        Returns:
            {"success": bool, "budget": float, "message": str}
        
        Raises:
            ValueError: If budget_amount is invalid or user doesn't exist
        """
        try:
            # Validate user exists
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Validate amount
            if not isinstance(budget_amount, (int, float, Decimal)):
                raise ValueError("Budget amount must be a number")
            
            budget_decimal = Decimal(str(budget_amount))
            if budget_decimal <= 0:
                raise ValueError("Budget must be greater than 0")
            if budget_decimal > Decimal("999999999.99"):
                raise ValueError("Budget cannot exceed $999,999,999.99")
            
            # Get or create setting
            setting = Setting.query.filter_by(
                user_id=user_id,
                key='monthly_budget'
            ).first()
            
            if setting:
                setting.value = str(float(budget_decimal))
            else:
                setting = Setting(
                    user_id=user_id,
                    key='monthly_budget',
                    value=str(float(budget_decimal))
                )
                db.session.add(setting)
            
            db.session.commit()
            
            return {
                "success": True,
                "budget": float(budget_decimal),
                "message": f"Budget set to ${float(budget_decimal):,.2f}"
            }
        
        except ValueError as ve:
            db.session.rollback()
            raise ve
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to set budget: {str(e)}")
    
    @staticmethod
    def get_budget(user_id: int) -> Dict[str, Any]:
        """
        Get the current budget for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            {
                "success": bool,
                "budget": float or None,
                "month_spent": float,
                "remaining": float or None,
                "percentage_used": float or None,
                "is_exceeded": bool,
                "message": str
            }
        """
        try:
            # Validate user exists
            user = User.query.get(user_id)
            if not user:
                raise ValueError(f"User {user_id} not found")
            
            # Get budget setting
            setting = Setting.query.filter_by(
                user_id=user_id,
                key='monthly_budget'
            ).first()
            
            if not setting:
                return {
                    "success": True,
                    "budget": None,
                    "month_spent": 0.0,
                    "remaining": None,
                    "percentage_used": None,
                    "is_exceeded": False,
                    "message": "No budget set"
                }
            
            try:
                budget = float(setting.value)
            except (ValueError, TypeError):
                return {
                    "success": False,
                    "message": "Invalid budget value in database"
                }
            
            # Calculate month's spending
            today = date.today()
            month_expenses = Expense.query.filter(
                Expense.user_id == user_id,
                Expense.date >= date(today.year, today.month, 1)
            ).all()
            
            month_spent = sum(float(e.amount) for e in month_expenses)
            remaining = budget - month_spent
            percentage_used = (month_spent / budget * 100) if budget > 0 else 0
            is_exceeded = month_spent > budget
            
            return {
                "success": True,
                "budget": budget,
                "month_spent": round(month_spent, 2),
                "remaining": round(remaining, 2),
                "percentage_used": round(percentage_used, 1),
                "is_exceeded": is_exceeded,
                "message": f"Budget: ${budget:,.2f}, Spent: ${month_spent:,.2f}"
            }
        
        except ValueError as ve:
            raise ve
        except Exception as e:
            raise Exception(f"Failed to get budget: {str(e)}")
    
    @staticmethod
    def check_budget_exceeds(user_id: int, threshold_percent: int = 80) -> Dict[str, Any]:
        """
        Check if user's spending exceeds budget threshold.
        
        Args:
            user_id: User ID
            threshold_percent: Percentage threshold (default 80% = warning)
        
        Returns:
            {
                "success": bool,
                "exceeds_threshold": bool,
                "alert_type": str ("none", "warning", "danger") or None,
                "percentage_used": float,
                "message": str
            }
        """
        try:
            result = BudgetService.get_budget(user_id)
            
            if not result["success"] or result["budget"] is None:
                return {
                    "success": True,
                    "exceeds_threshold": False,
                    "alert_type": "none",
                    "percentage_used": 0,
                    "message": "No budget set"
                }
            
            percentage = result["percentage_used"]
            
            if result["is_exceeded"]:
                alert_type = "danger"
            elif percentage > threshold_percent:
                alert_type = "warning"
            else:
                alert_type = "none"
            
            return {
                "success": True,
                "exceeds_threshold": alert_type != "none",
                "alert_type": alert_type,
                "percentage_used": percentage,
                "message": f"Spending is at {percentage}% of budget"
            }
        
        except Exception as e:
            raise Exception(f"Failed to check budget threshold: {str(e)}")
    
    @staticmethod
    def get_budget_status(user_id: int) -> Dict[str, Any]:
        """
        Get detailed budget status for dashboard display.
        
        Args:
            user_id: User ID
        
        Returns:
            {
                "success": bool,
                "budget_set": bool,
                "budget": float or None,
                "spent": float,
                "remaining": float,
                "percentage": float,
                "status": str ("ok", "warning", "exceeded"),
                "message": str
            }
        """
        try:
            result = BudgetService.get_budget(user_id)
            
            if not result["success"]:
                return {
                    "success": False,
                    "message": result.get("message", "Error getting budget")
                }
            
            budget = result["budget"]
            
            if budget is None:
                return {
                    "success": True,
                    "budget_set": False,
                    "budget": None,
                    "spent": result["month_spent"],
                    "remaining": None,
                    "percentage": 0,
                    "status": "ok",
                    "message": "No monthly budget set"
                }
            
            percentage = result["percentage_used"]
            
            if result["is_exceeded"]:
                status = "exceeded"
            elif percentage > 80:
                status = "warning"
            else:
                status = "ok"
            
            return {
                "success": True,
                "budget_set": True,
                "budget": budget,
                "spent": result["month_spent"],
                "remaining": result["remaining"],
                "percentage": percentage,
                "status": status,
                "message": f"Budget status: {status.upper()}"
            }
        
        except Exception as e:
            raise Exception(f"Failed to get budget status: {str(e)}")
    
    @staticmethod
    def create_budget_alert(user_id: int, alert_type: str, percentage_used: float) -> Dict[str, Any]:
        """
        Create a budget alert if conditions warrant.
        
        Args:
            user_id: User ID
            alert_type: "warning" or "danger"
            percentage_used: Percentage of budget used (0-100+)
        
        Returns:
            {"success": bool, "alert_created": bool, "alert_id": int or None, "message": str}
        """
        try:
            # Get budget info
            result = BudgetService.get_budget(user_id)
            if not result["success"] or result["budget"] is None:
                return {
                    "success": True,
                    "alert_created": False,
                    "alert_id": None,
                    "message": "No budget set, no alert created"
                }
            
            budget = result["budget"]
            month_spent = result["month_spent"]
            today = date.today()
            current_month = f"{today.year}-{today.month:02d}"
            
            # Check if alert already exists
            existing_alert = Alert.query.filter_by(
                user_id=user_id,
                triggered_month=current_month,
                alert_type=f'budget_{alert_type}' if alert_type in ['warning', 'danger'] else alert_type
            ).first()
            
            if existing_alert:
                return {
                    "success": True,
                    "alert_created": False,
                    "alert_id": existing_alert.id,
                    "message": f"Alert already exists for {current_month}"
                }
            
            # Create alert
            if alert_type == "danger":
                exceeded_by = month_spent - budget
                percentage_over = (month_spent / budget - 1) * 100
                title = "Budget Exceeded! 🚨"
                message = f"You've spent ${month_spent:,.2f}, exceeding your ${budget:,.2f} budget by ${exceeded_by:,.2f} ({percentage_over:.1f}%)"
                severity = "danger"
            elif alert_type == "warning":
                remaining = budget - month_spent
                title = "Budget Warning ⚠️"
                message = f"You've spent ${month_spent:,.2f} ({percentage_used:.1f}%) of your ${budget:,.2f} budget. ${remaining:,.2f} remaining."
                severity = "warning"
            else:
                return {
                    "success": False,
                    "message": f"Invalid alert type: {alert_type}"
                }
            
            alert = Alert(
                user_id=user_id,
                alert_type=f'budget_{alert_type}',
                title=title,
                message=message,
                severity=severity,
                triggered_month=current_month
            )
            
            db.session.add(alert)
            db.session.commit()
            
            return {
                "success": True,
                "alert_created": True,
                "alert_id": alert.id,
                "message": f"Budget {alert_type} alert created"
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to create budget alert: {str(e)}")
    
    @staticmethod
    def reset_monthly_alerts(user_id: int, current_month: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear monthly alerts for a user (useful for new month).
        
        Args:
            user_id: User ID
            current_month: Month string in YYYY-MM format (defaults to today)
        
        Returns:
            {"success": bool, "alerts_deleted": int, "message": str}
        """
        try:
            if not current_month:
                today = date.today()
                current_month = f"{today.year}-{today.month:02d}"
            
            # Delete all budget alerts for this month
            alerts = Alert.query.filter_by(
                user_id=user_id,
                triggered_month=current_month
            ).filter(Alert.alert_type.like('budget_%')).all()
            
            count = len(alerts)
            for alert in alerts:
                db.session.delete(alert)
            
            db.session.commit()
            
            return {
                "success": True,
                "alerts_deleted": count,
                "message": f"Cleared {count} budget alerts for {current_month}"
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f"Failed to reset alerts: {str(e)}")
