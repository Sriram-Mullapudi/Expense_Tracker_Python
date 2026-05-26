"""
Unit tests for database models
Tests model creation, relationships, and business logic
"""

import pytest
from datetime import datetime, date
from app import app, db
from models import User, Expense, Alert, Setting


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
        password='hashed_password'
    )
    db.session.add(user)
    db.session.commit()
    return user


class TestUserModel:
    """Test User model"""
    
    def test_create_user(self, client):
        """User can be created"""
        user = User(
            username='john',
            email='john@example.com',
            password='hashed'
        )
        db.session.add(user)
        db.session.commit()
        
        assert user.id is not None
        assert user.username == 'john'
        assert user.email == 'john@example.com'
    
    def test_user_default_role(self, client, test_user):
        """New users have 'user' role by default"""
        assert test_user.role == 'user'
    
    def test_user_is_admin(self, client):
        """is_admin() returns True only for admin users"""
        user = User(username='user1', password='pass', role='user')
        admin = User(username='admin1', password='pass', role='admin')
        
        db.session.add_all([user, admin])
        db.session.commit()
        
        assert user.is_admin() is False
        assert admin.is_admin() is True
    
    def test_user_created_at_timestamp(self, client):
        """User has created_at timestamp"""
        user = User(username='test', password='pass')
        db.session.add(user)
        db.session.commit()
        
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)
    
    def test_user_unique_username(self, client, test_user):
        """Username must be unique"""
        duplicate = User(
            username='testuser',  # Same as test_user
            email='other@example.com',
            password='hashed'
        )
        db.session.add(duplicate)
        
        with pytest.raises(Exception):  # IntegrityError
            db.session.commit()
    
    def test_user_cascade_delete_expenses(self, client, test_user):
        """Deleting user also deletes their expenses"""
        expense = Expense(
            user_id=test_user.id,
            title='Lunch',
            category='Food',
            amount=10.0,
            date=date.today()
        )
        db.session.add(expense)
        db.session.commit()
        
        expense_id = expense.id
        
        # Delete user
        db.session.delete(test_user)
        db.session.commit()
        
        # Expense should be deleted
        assert db.session.get(Expense, expense_id) is None
    
    def test_user_cascade_delete_alerts(self, client, test_user):
        """Deleting user also deletes their alerts"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            title='Budget Warning',
            message='You have exceeded your budget',
            severity='warning'
        )
        db.session.add(alert)
        db.session.commit()
        
        alert_id = alert.id
        
        # Delete user
        db.session.delete(test_user)
        db.session.commit()
        
        # Alert should be deleted
        assert db.session.get(Alert, alert_id) is None


class TestExpenseModel:
    """Test Expense model"""
    
    def test_create_expense(self, client, test_user):
        """Expense can be created"""
        expense = Expense(
            user_id=test_user.id,
            title='Coffee',
            amount=3.50,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        assert expense.id is not None
        assert expense.title == 'Coffee'
        assert expense.amount == 3.50
    
    def test_expense_belongs_to_user(self, client, test_user):
        """Expense is associated with correct user"""
        expense = Expense(
            user_id=test_user.id,
            title='Test',
            category='Test',
            amount=5.0,
            date=date.today()
        )
        db.session.add(expense)
        db.session.commit()
        
        assert expense.user_id == test_user.id
        assert expense in test_user.expenses
    
    def test_expense_requires_amount(self, client, test_user):
        """Expense requires amount"""
        expense = Expense(
            user_id=test_user.id,
            title='Invalid',
            date=date.today()
            # amount missing
        )
        db.session.add(expense)
        
        with pytest.raises(Exception):  # IntegrityError
            db.session.commit()
    
    def test_multiple_expenses_for_user(self, client, test_user):
        """User can have multiple expenses"""
        exp1 = Expense(user_id=test_user.id, title='Lunch', category='Food', amount=10, date=date.today())
        exp2 = Expense(user_id=test_user.id, title='Gas', category='Transport', amount=30, date=date.today())
        exp3 = Expense(user_id=test_user.id, title='Movie', category='Entertainment', amount=15, date=date.today())
        
        db.session.add_all([exp1, exp2, exp3])
        db.session.commit()
        
        assert len(test_user.expenses) == 3
        assert exp1 in test_user.expenses
        assert exp2 in test_user.expenses
        assert exp3 in test_user.expenses


class TestAlertModel:
    """Test Alert model"""
    
    def test_create_alert(self, client, test_user):
        """Alert can be created"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            title='Budget Warning',
            message='You have exceeded your budget',
            severity='warning'
        )
        db.session.add(alert)
        db.session.commit()
        
        assert alert.id is not None
        assert alert.alert_type == 'budget_warning'
    
    def test_alert_triggered_month(self, client, test_user):
        """Alert tracks triggered month"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            title='Budget Warning',
            message='You have exceeded your budget',
            severity='warning',
            triggered_month='2024-01'
        )
        db.session.add(alert)
        db.session.commit()
        
        assert alert.triggered_month == '2024-01'
    
    def test_alert_default_is_sent_false(self, client, test_user):
        """New alerts have is_sent=False"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            title='Budget Warning',
            message='You have exceeded your budget',
            severity='warning'
        )
        db.session.add(alert)
        db.session.commit()
        
        assert alert.is_sent is False
    
    def test_alert_created_at_timestamp(self, client, test_user):
        """Alert has created_at timestamp"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            title='Budget Warning',
            message='You have exceeded your budget',
            severity='warning'
        )
        db.session.add(alert)
        db.session.commit()
        
        assert alert.created_at is not None
        assert isinstance(alert.created_at, datetime)


class TestSettingModel:
    """Test Setting model"""
    
    def test_create_setting(self, client, test_user):
        """Setting can be created"""
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='1000'
        )
        db.session.add(setting)
        db.session.commit()
        
        assert setting.id is not None
        assert setting.key == 'monthly_budget'
        assert setting.value == '1000'
    
    def test_get_setting_by_key(self, client, test_user):
        """Settings can be retrieved by key"""
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='1000'
        )
        db.session.add(setting)
        db.session.commit()
        
        retrieved = Setting.query.filter_by(
            user_id=test_user.id,
            key='monthly_budget'
        ).first()
        
        assert retrieved is not None
        assert retrieved.value == '1000'


class TestRelationships:
    """Test model relationships and cascading"""
    
    def test_user_has_many_expenses(self, client, test_user):
        """One user has many expenses"""
        for i in range(5):
            expense = Expense(
                user_id=test_user.id,
                title=f'Expense {i}',
                category='Food',
                amount=10 * (i + 1),
                date=date.today()
            )
            db.session.add(expense)
        db.session.commit()
        
        assert len(test_user.expenses) == 5
    
    def test_user_has_many_alerts(self, client, test_user):
        """One user has many alerts"""
        for i in range(3):
            alert = Alert(
                user_id=test_user.id,
                alert_type='budget_warning',
                title=f'Alert {i}',
                message=f'Message {i}',
                severity='warning'
            )
            db.session.add(alert)
        db.session.commit()
        
        assert len(test_user.alerts) == 3
