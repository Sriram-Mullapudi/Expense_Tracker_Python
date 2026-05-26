"""Repository layer - data access abstraction for models.

This layer provides a uniform interface for all database operations.
Services use repositories instead of direct db.session queries.
Benefits: Testable (can mock repositories), query optimization centralized.
"""
from typing import List, Optional, Any, Dict, TypeVar, Generic
from datetime import date, datetime
from decimal import Decimal

from models import db, User, Expense, Setting, Alert

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository class with common CRUD operations."""
    
    def __init__(self, model):
        self.model = model
    
    def create(self, **kwargs) -> T:
        """Create a new record."""
        instance = self.model(**kwargs)
        db.session.add(instance)
        db.session.commit()
        return instance
    
    def get_by_id(self, id: int) -> Optional[T]:
        """Get record by ID."""
        return self.model.query.get(id)
    
    def get_all(self) -> List[T]:
        """Get all records."""
        return self.model.query.all()
    
    def update(self, instance: T, **kwargs) -> T:
        """Update record."""
        for key, value in kwargs.items():
            if hasattr(instance, key):
                setattr(instance, key, value)
        db.session.commit()
        return instance
    
    def delete(self, instance: T) -> bool:
        """Delete record."""
        db.session.delete(instance)
        db.session.commit()
        return True
    
    def delete_by_id(self, id: int) -> bool:
        """Delete record by ID."""
        instance = self.get_by_id(id)
        if instance:
            return self.delete(instance)
        return False


class UserRepository(BaseRepository[User]):
    """Repository for User model operations."""
    
    def __init__(self):
        super().__init__(User)
    
    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return User.query.filter_by(username=username.lower()).first()
    
    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return User.query.filter_by(email=email.lower()).first()
    
    def get_by_reset_token(self, token: str) -> Optional[User]:
        """Get user by password reset token."""
        return User.query.filter_by(reset_token=token).first()
    
    def username_exists(self, username: str) -> bool:
        """Check if username exists."""
        return User.query.filter_by(username=username.lower()).first() is not None
    
    def email_exists(self, email: str) -> bool:
        """Check if email exists."""
        return User.query.filter_by(email=email.lower()).first() is not None


class ExpenseRepository(BaseRepository[Expense]):
    """Repository for Expense model operations."""
    
    def __init__(self):
        super().__init__(Expense)
    
    def get_user_expenses(self, user_id: int) -> List[Expense]:
        """Get all expenses for a user."""
        return Expense.query.filter_by(user_id=user_id).order_by(Expense.date.desc()).all()
    
    def get_user_expense_by_id(self, user_id: int, expense_id: int) -> Optional[Expense]:
        """Get specific expense for user (with ownership check)."""
        return Expense.query.filter_by(
            user_id=user_id,
            id=expense_id
        ).first()
    
    def get_user_expenses_by_category(self, user_id: int, category: str) -> List[Expense]:
        """Get expenses for user in specific category."""
        return Expense.query.filter_by(
            user_id=user_id,
            category=category
        ).order_by(Expense.date.desc()).all()
    
    def get_user_expenses_by_date_range(
        self, user_id: int, date_from: date, date_to: date
    ) -> List[Expense]:
        """Get expenses for user within date range."""
        return Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date >= date_from,
            Expense.date <= date_to
        ).order_by(Expense.date.desc()).all()
    
    def get_user_expenses_by_month(self, user_id: int, year: int, month: int) -> List[Expense]:
        """Get expenses for user in specific month."""
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        return Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date >= date(year, month, 1),
            Expense.date <= date(year, month, last_day)
        ).order_by(Expense.date.desc()).all()
    
    def get_month_total(self, user_id: int, year: int, month: int) -> float:
        """Get total spending for user in specific month."""
        expenses = self.get_user_expenses_by_month(user_id, year, month)
        return sum(float(e.amount) for e in expenses)
    
    def get_today_total(self, user_id: int) -> float:
        """Get total spending for user today."""
        today = date.today()
        expenses = Expense.query.filter(
            Expense.user_id == user_id,
            Expense.date == today
        ).all()
        return sum(float(e.amount) for e in expenses)
    
    def get_categories_for_user(self, user_id: int) -> List[str]:
        """Get list of categories used by user."""
        results = db.session.query(Expense.category).filter_by(
            user_id=user_id
        ).distinct().all()
        return [r[0] for r in results]
    
    def get_category_breakdown(self, user_id: int, year: int, month: int) -> Dict[str, float]:
        """Get spending breakdown by category for user in month."""
        from sqlalchemy import func
        
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        
        results = db.session.query(
            Expense.category,
            func.sum(Expense.amount)
        ).filter(
            Expense.user_id == user_id,
            Expense.date >= date(year, month, 1),
            Expense.date <= date(year, month, last_day)
        ).group_by(Expense.category).all()
        
        return {category: float(amount) for category, amount in results}
    
    def delete_user_expenses(self, user_id: int) -> int:
        """Delete all expenses for a user."""
        expenses = Expense.query.filter_by(user_id=user_id).all()
        count = len(expenses)
        for expense in expenses:
            db.session.delete(expense)
        db.session.commit()
        return count


class SettingRepository(BaseRepository[Setting]):
    """Repository for Setting model operations."""
    
    def __init__(self):
        super().__init__(Setting)
    
    def get_user_setting(self, user_id: int, key: str) -> Optional[Setting]:
        """Get specific setting for user."""
        return Setting.query.filter_by(user_id=user_id, key=key).first()
    
    def get_user_settings(self, user_id: int) -> List[Setting]:
        """Get all settings for user."""
        return Setting.query.filter_by(user_id=user_id).all()
    
    def get_setting_value(self, user_id: int, key: str, default: str = '') -> str:
        """Get setting value or default."""
        setting = self.get_user_setting(user_id, key)
        return setting.value if setting else default
    
    def set_setting(self, user_id: int, key: str, value: str) -> Setting:
        """Set or create setting."""
        setting = self.get_user_setting(user_id, key)
        if setting:
            return self.update(setting, value=value)
        else:
            return self.create(user_id=user_id, key=key, value=value)
    
    def delete_user_settings(self, user_id: int) -> int:
        """Delete all settings for user."""
        settings = self.get_user_settings(user_id)
        count = len(settings)
        for setting in settings:
            db.session.delete(setting)
        db.session.commit()
        return count


class AlertRepository(BaseRepository[Alert]):
    """Repository for Alert model operations."""
    
    def __init__(self):
        super().__init__(Alert)
    
    def get_user_alerts(self, user_id: int) -> List[Alert]:
        """Get all alerts for user."""
        return Alert.query.filter_by(user_id=user_id).all()
    
    def get_active_alerts(self, user_id: int) -> List[Alert]:
        """Get active (unresolved) alerts for user."""
        return Alert.query.filter_by(user_id=user_id, resolved=False).all()
    
    def get_alert_by_month(self, user_id: int, month: str, alert_type: str) -> Optional[Alert]:
        """Get specific alert for user in month (alert_type like 'budget_exceeded')."""
        return Alert.query.filter_by(
            user_id=user_id,
            triggered_month=month,
            alert_type=alert_type
        ).first()
    
    def get_monthly_alerts(self, user_id: int, month: str) -> List[Alert]:
        """Get all alerts for user in month."""
        return Alert.query.filter_by(user_id=user_id, triggered_month=month).all()
    
    def mark_resolved(self, alert: Alert) -> Alert:
        """Mark alert as resolved."""
        return self.update(alert, resolved=True)
    
    def delete_monthly_alerts(self, user_id: int, month: str) -> int:
        """Delete all alerts for user in month."""
        alerts = self.get_monthly_alerts(user_id, month)
        count = len(alerts)
        for alert in alerts:
            db.session.delete(alert)
        db.session.commit()
        return count
    
    def delete_user_alerts(self, user_id: int) -> int:
        """Delete all alerts for user."""
        alerts = self.get_user_alerts(user_id)
        count = len(alerts)
        for alert in alerts:
            db.session.delete(alert)
        db.session.commit()
        return count


# Factory/Singleton instances for use in services
user_repo = UserRepository()
expense_repo = ExpenseRepository()
setting_repo = SettingRepository()
alert_repo = AlertRepository()
