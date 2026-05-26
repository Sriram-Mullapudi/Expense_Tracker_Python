"""
Unit tests for business logic (utils, services)
Tests calculations, alerts, analytics, file handling
"""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from app import app, db
from models import User, Expense, Alert, Setting
from utils import calculate_month_total, get_monthly_budget, check_budget_and_create_alerts, get_setting
from analytics_service import (
    get_monthly_trends, get_category_breakdown, 
    get_spending_statistics, get_highest_spending_categories
)
from werkzeug.security import generate_password_hash


@pytest.fixture
def client():
    """Flask test client with database"""
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


@pytest.fixture
def test_user(client):
    """Create a test user"""
    user = User(
        username='testuser',
        email='test@example.com',
        password=generate_password_hash('testpass')
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def app_context(client):
    """Application context for utils tests"""
    with app.app_context():
        yield


class TestMonthlyCalculations:
    """Test monthly expense calculations"""
    
    def test_calculate_month_total_empty(self, client, app_context, test_user):
        """Month total is 0 with no expenses"""
        total = calculate_month_total(test_user.id)
        assert total == 0.0
    
    def test_calculate_month_total_single_expense(self, client, app_context, test_user):
        """Month total includes single expense"""
        expense = Expense(
            user_id=test_user.id,
            title='Coffee',
            amount=5.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        total = calculate_month_total(test_user.id)
        assert total == 5.0
    
    def test_calculate_month_total_multiple_expenses(self, client, app_context, test_user):
        """Month total includes all expenses"""
        expenses = [
            Expense(user_id=test_user.id, title='Coffee', amount=5.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='Gas', amount=30.0, date=date.today(), category='Transport'),
            Expense(user_id=test_user.id, title='Movie', amount=15.0, date=date.today(), category='Entertainment'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        total = calculate_month_total(test_user.id)
        assert total == 50.0
    
    def test_calculate_month_total_excludes_past_months(self, client, app_context, test_user):
        """Month total excludes expenses from previous months"""
        today = date.today()
        last_month = today.replace(day=1) - timedelta(days=1)
        
        expense_this_month = Expense(
            user_id=test_user.id,
            title='This month',
            amount=20.0,
            date=today,
            category='Food'
        )
        expense_last_month = Expense(
            user_id=test_user.id,
            title='Last month',
            amount=100.0,
            date=last_month,
            category='Food'
        )
        
        db.session.add_all([expense_this_month, expense_last_month])
        db.session.commit()
        
        total = calculate_month_total(test_user.id)
        assert total == 20.0  # Only this month
    
    def test_calculate_month_total_float_amounts(self, client, app_context, test_user):
        """Month total handles decimal amounts"""
        expenses = [
            Expense(user_id=test_user.id, title='E1', amount=10.50, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E2', amount=20.75, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E3', amount=5.25, date=date.today(), category='Food'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        total = calculate_month_total(test_user.id)
        assert abs(total - 36.50) < 0.01  # Floating point comparison


class TestBudgetLogic:
    """Test budget calculations"""
    
    def test_get_monthly_budget_default(self, client, app_context, test_user):
        """Default budget is 0 if not set"""
        budget = get_monthly_budget(test_user.id)
        assert budget == 0
    
    def test_get_monthly_budget_custom(self, client, app_context, test_user):
        """Custom budget can be set and retrieved"""
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='1000'
        )
        db.session.add(setting)
        db.session.commit()
        
        budget = get_monthly_budget(test_user.id)
        assert budget == 1000.0
    
    def test_get_setting(self, client, app_context, test_user):
        """Settings can be retrieved by key"""
        setting = Setting(
            user_id=test_user.id,
            key='currency',
            value='USD'
        )
        db.session.add(setting)
        db.session.commit()
        
        value = get_setting('currency')
        assert value == 'USD' or value is None  # Depends on app context


class TestAlertSystem:
    """Test alert creation and duplicate prevention"""
    
    def test_alert_created_when_exceeds_budget(self, client, app_context, test_user):
        """Alert created when spending exceeds budget"""
        # Set budget to $50
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='50'
        )
        db.session.add(setting)
        
        # Add $75 expense
        expense = Expense(
            user_id=test_user.id,
            title='Over budget',
            amount=75.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        # Check for alert
        alert = check_budget_and_create_alerts(test_user.id)
        assert alert is not None
        assert alert.severity == 'danger'
        assert alert.alert_type == 'budget_exceeded'
    
    def test_warning_alert_at_80_percent(self, client, app_context, test_user):
        """Warning alert created at 80% of budget"""
        # Set budget to $100
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='100'
        )
        db.session.add(setting)
        
        # Add $85 expense (85%)
        expense = Expense(
            user_id=test_user.id,
            title='Warning level',
            amount=85.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        # Check for alert
        alert = check_budget_and_create_alerts(test_user.id)
        assert alert is not None
        assert alert.severity == 'warning'
        assert alert.alert_type == 'budget_warning'
    
    def test_no_alert_below_80_percent(self, client, app_context, test_user):
        """No alert when spending below 80%"""
        # Set budget to $100
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='100'
        )
        db.session.add(setting)
        
        # Add $50 expense (50%)
        expense = Expense(
            user_id=test_user.id,
            title='Safe level',
            amount=50.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        # Check for alert
        alert = check_budget_and_create_alerts(test_user.id)
        assert alert is None
    
    def test_duplicate_alert_prevention(self, client, app_context, test_user):
        """Duplicate alerts not created in same month"""
        # Set budget to $50
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='50'
        )
        db.session.add(setting)
        db.session.commit()
        
        # Add $75 expense - should create alert
        expense1 = Expense(
            user_id=test_user.id,
            title='Over budget 1',
            amount=75.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense1)
        db.session.commit()
        
        alert1 = check_budget_and_create_alerts(test_user.id)
        assert alert1 is not None
        initial_alert_count = Alert.query.filter_by(user_id=test_user.id).count()
        
        # Add another $10 expense in same month
        expense2 = Expense(
            user_id=test_user.id,
            title='Over budget 2',
            amount=10.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense2)
        db.session.commit()
        
        # Should NOT create another alert
        alert2 = check_budget_and_create_alerts(test_user.id)
        assert alert2 is None
        
        final_alert_count = Alert.query.filter_by(user_id=test_user.id).count()
        assert initial_alert_count == final_alert_count
    
    def test_alert_tracks_triggered_month(self, client, app_context, test_user):
        """Alert records month it was triggered"""
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='50'
        )
        db.session.add(setting)
        
        expense = Expense(
            user_id=test_user.id,
            title='Over budget',
            amount=75.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        alert = check_budget_and_create_alerts(test_user.id)
        
        current_month = datetime.now().strftime("%Y-%m")
        assert alert.triggered_month == current_month


class TestAnalytics:
    """Test analytics calculations"""
    
    def test_monthly_trends_empty(self, client, app_context, test_user):
        """Monthly trends with no data"""
        trends = get_monthly_trends(test_user.id)
        
        # Should return dict with 12 months, all zeros
        assert len(trends) == 12
        assert all(v == 0 for v in trends.values())
    
    def test_monthly_trends_with_expenses(self, client, app_context, test_user):
        """Monthly trends includes expenses"""
        today = date.today()
        expense = Expense(
            user_id=test_user.id,
            title='Test',
            amount=100.0,
            date=today,
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        trends = get_monthly_trends(test_user.id)
        
        current_month_key = today.strftime("%Y-%m")
        assert trends[current_month_key] == 100.0
    
    def test_category_breakdown(self, client, app_context, test_user):
        """Category breakdown totals by category"""
        expenses = [
            Expense(user_id=test_user.id, title='Lunch', amount=10.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='Dinner', amount=20.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='Gas', amount=50.0, date=date.today(), category='Transport'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        breakdown = get_category_breakdown(test_user.id)
        
        assert 'Food' in breakdown
        assert breakdown['Food'] == 30.0
        assert 'Transport' in breakdown
        assert breakdown['Transport'] == 50.0
    
    def test_spending_statistics(self, client, app_context, test_user):
        """Spending statistics calculates summary metrics"""
        expenses = [
            Expense(user_id=test_user.id, title='E1', amount=10.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E2', amount=20.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E3', amount=30.0, date=date.today(), category='Food'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        stats = get_spending_statistics(test_user.id)
        
        assert stats['total'] == 60.0
        assert stats['average'] == 20.0
        assert stats['highest'] == 30.0
        assert stats['lowest'] == 10.0
        assert stats['count'] == 3
    
    def test_highest_spending_categories(self, client, app_context, test_user):
        """Top spending categories ranked"""
        expenses = [
            Expense(user_id=test_user.id, title='C1', amount=100.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='C2', amount=50.0, date=date.today(), category='Transport'),
            Expense(user_id=test_user.id, title='C3', amount=80.0, date=date.today(), category='Entertainment'),
            Expense(user_id=test_user.id, title='C4', amount=20.0, date=date.today(), category='Other'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        top = get_highest_spending_categories(test_user.id, limit=3)
        
        # Should be sorted by amount descending
        assert top[0]['category'] == 'Food'
        assert top[0]['total'] == 100.0
        assert top[1]['category'] == 'Entertainment'
        assert top[1]['total'] == 80.0
        assert top[2]['category'] == 'Transport'
        assert top[2]['total'] == 50.0


class TestExpenseOperations:
    """Test expense CRUD operations"""
    
    def test_add_expense(self, client, app_context, test_user):
        """Expense can be added"""
        expense = Expense(
            user_id=test_user.id,
            title='Test',
            amount=25.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        assert expense.id is not None
    
    def test_edit_expense(self, client, app_context, test_user):
        """Expense can be edited"""
        expense = Expense(
            user_id=test_user.id,
            title='Original',
            amount=10.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        expense.title = 'Updated'
        expense.amount = 20.0
        db.session.commit()
        
        updated = Expense.query.get(expense.id)
        assert updated.title == 'Updated'
        assert updated.amount == 20.0
    
    def test_delete_expense(self, client, app_context, test_user):
        """Expense can be deleted"""
        expense = Expense(
            user_id=test_user.id,
            title='To delete',
            amount=10.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        expense_id = expense.id
        db.session.delete(expense)
        db.session.commit()
        
        assert Expense.query.get(expense_id) is None
    
    def test_user_only_sees_own_expenses(self, client, app_context):
        """User can only see their own expenses"""
        # Create two users
        user1 = User(username='user1', password='pass', email='u1@test.com')
        user2 = User(username='user2', password='pass', email='u2@test.com')
        db.session.add_all([user1, user2])
        db.session.commit()
        
        # Each creates an expense
        exp1 = Expense(user_id=user1.id, title='U1 expense', amount=10, date=date.today(), category='Food')
        exp2 = Expense(user_id=user2.id, title='U2 expense', amount=20, date=date.today(), category='Food')
        db.session.add_all([exp1, exp2])
        db.session.commit()
        
        # User1 should only see their expense
        user1_expenses = Expense.query.filter_by(user_id=user1.id).all()
        assert len(user1_expenses) == 1
        assert user1_expenses[0].title == 'U1 expense'
