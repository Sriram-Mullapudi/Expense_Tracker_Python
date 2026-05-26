"""Comprehensive test suite for service layer and repository layer.

These tests validate all business logic without requiring Flask context
(except where minimal Flask operations occur).
"""
import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from pydantic import ValidationError
from werkzeug.security import generate_password_hash

from app import create_app
from models import db, User, Expense, Setting, Alert
from services import AuthService, ExpenseService, BudgetService
from services.validators import (
    LoginRequest, RegisterRequest, ExpenseCreateRequest,
    ExpenseUpdateRequest, ExpenseFilterRequest, BudgetSetRequest
)
from repositories import (
    user_repo, expense_repo, setting_repo, alert_repo
)


@pytest.fixture
def app():
    """Create application for testing."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create test user."""
    with app.app_context():
        password_hash = generate_password_hash('TestPass123!', method='pbkdf2:sha256', salt_length=16)
        user = User(
            username='testuser',
            email='test@example.com',
            password=password_hash,
            role='user'
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id  # Store ID before context closes
        db.session.expunge(user)  # Detach from session
    
    # Return a simple object with id attribute to avoid DetachedInstanceError
    class UserStub:
        def __init__(self, id):
            self.id = id
    
    return UserStub(user_id)


@pytest.fixture
def test_user_with_budget(app, test_user):
    """Create test user with budget set."""
    with app.app_context():
        setting = Setting(
            user_id=test_user.id,
            key='monthly_budget',
            value='1000'
        )
        db.session.add(setting)
        db.session.commit()
        return test_user


@pytest.fixture
def test_expenses(app, test_user):
    """Create test expenses."""
    with app.app_context():
        today = date.today()
        expenses_data = [
            {
                'user_id': test_user.id,
                'date': today,
                'title': 'Groceries',
                'category': 'Food',
                'amount': 50.00,
                'description': 'Weekly groceries'
            },
            {
                'user_id': test_user.id,
                'date': today - timedelta(days=1),
                'title': 'Gas',
                'category': 'Transport',
                'amount': 40.00,
                'description': 'Fill tank'
            },
            {
                'user_id': test_user.id,
                'date': today - timedelta(days=3),  # Changed from 10 to 3 to stay in same month
                'title': 'Movie',
                'category': 'Entertainment',
                'amount': 15.00,
                'description': 'Cinema'
            }
        ]
        expenses = []
        for exp_data in expenses_data:
            exp = Expense(**exp_data)
            db.session.add(exp)
        db.session.commit()
        
        # Store IDs and detach
        expense_ids = [exp.id for exp in db.session.query(Expense).filter(Expense.user_id == test_user.id).all()]
        
        # Return stubs instead of detached objects
        class ExpenseStub:
            def __init__(self, id):
                self.id = id
        
        return [ExpenseStub(exp_id) for exp_id in expense_ids]


# ============ VALIDATOR TESTS ============

class TestValidators:
    """Test Pydantic validators."""
    
    def test_login_request_valid(self):
        """Valid login should pass."""
        req = LoginRequest(username='testuser', password='pass123')
        assert req.username == 'testuser'
    
    def test_login_request_invalid_username_length(self):
        """Username too short should fail."""
        with pytest.raises(ValidationError):
            LoginRequest(username='ab', password='pass123')
    
    def test_register_request_password_strength(self):
        """Weak password should fail."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username='testuser',
                email='test@example.com',
                password='weak',  # Too short and no complexity
                confirm_password='weak'
            )
    
    def test_register_request_passwords_match(self):
        """Passwords must match."""
        with pytest.raises(ValidationError):
            RegisterRequest(
                username='testuser',
                email='test@example.com',
                password='StrongPass123!',
                confirm_password='Different123!'
            )
    
    def test_expense_create_request_valid(self):
        """Valid expense should pass."""
        req = ExpenseCreateRequest(
            title='Test',
            category='Food',
            amount=25.50,
            date=date.today(),
            description='Test expense'
        )
        assert req.title == 'Test'
    
    def test_expense_create_request_future_date(self):
        """Future date should fail."""
        tomorrow = date.today() + timedelta(days=1)
        with pytest.raises(ValidationError):
            ExpenseCreateRequest(
                title='Test',
                category='Food',
                amount=25.50,
                date=tomorrow
            )
    
    def test_expense_filter_request_invalid_month(self):
        """Invalid month format should fail."""
        with pytest.raises(ValidationError):
            ExpenseFilterRequest(month='2024-13')  # Invalid month
    
    def test_budget_set_request_valid(self):
        """Valid budget should pass."""
        req = BudgetSetRequest(budget_amount=1000.00)
        assert req.budget_amount == 1000.00
    
    def test_budget_set_request_negative(self):
        """Negative budget should fail."""
        with pytest.raises(ValidationError):
            BudgetSetRequest(budget_amount=-100)


# ============ EXPENSE SERVICE TESTS ============

class TestExpenseService:
    """Test ExpenseService methods."""
    
    def test_create_expense_valid(self, app, test_user):
        """Creating valid expense should succeed."""
        with app.app_context():
            result = ExpenseService.create_expense(
                user_id=test_user.id,
                title='Lunch',
                category='Food',
                amount=12.50,
                date_obj=date.today(),
                description='Lunch at cafe'
            )
            assert result['success'] == True
            assert result['expense']['title'] == 'Lunch'
    
    def test_create_expense_invalid_amount(self, app, test_user):
        """Creating expense with negative amount should fail."""
        with app.app_context():
            with pytest.raises(ValueError):
                ExpenseService.create_expense(
                    user_id=test_user.id,
                    title='Lunch',
                    category='Food',
                    amount=-10.00,  # Invalid
                    date_obj=date.today()
                )
    
    def test_get_expense_valid(self, app, test_user, test_expenses):
        """Getting valid expense should succeed."""
        with app.app_context():
            expense = test_expenses[0]
            result = ExpenseService.get_expense(
                user_id=test_user.id,
                expense_id=expense.id
            )
            assert result['success'] == True
            assert result['expense']['title'] == 'Groceries'
    
    def test_get_expense_unauthorized(self, app, test_user, test_expenses):
        """Getting expense from different user should fail."""
        with app.app_context():
            # Create another user with proper password hash
            password_hash = generate_password_hash('OtherPass123!', method='pbkdf2:sha256', salt_length=16)
            other_user = User(
                username='otheruser',
                email='other@example.com',
                password=password_hash
            )
            db.session.add(other_user)
            db.session.commit()
            
            expense = test_expenses[0]
            with pytest.raises(ValueError, match="not authorized"):
                ExpenseService.get_expense(
                    user_id=other_user.id,
                    expense_id=expense.id
                )
    
    def test_update_expense_valid(self, app, test_user, test_expenses):
        """Updating valid expense should succeed."""
        with app.app_context():
            expense = test_expenses[0]
            result = ExpenseService.update_expense(
                user_id=test_user.id,
                expense_id=expense.id,
                title='Updated Groceries'
            )
            assert result['success'] == True
            assert result['expense']['title'] == 'Updated Groceries'
    
    def test_delete_expense_valid(self, app, test_user, test_expenses):
        """Deleting valid expense should succeed."""
        with app.app_context():
            expense = test_expenses[0]
            result = ExpenseService.delete_expense(
                user_id=test_user.id,
                expense_id=expense.id
            )
            assert result['success'] == True
            # Verify it's deleted
            assert Expense.query.get(expense.id) is None
    
    def test_list_expenses_all(self, app, test_user, test_expenses):
        """Listing all expenses should return all."""
        with app.app_context():
            result = ExpenseService.list_expenses(
                user_id=test_user.id
            )
            assert result['success'] == True
            assert len(result['expenses']) == 3
    
    def test_list_expenses_by_category(self, app, test_user, test_expenses):
        """Filtering by category should work."""
        with app.app_context():
            result = ExpenseService.list_expenses(
                user_id=test_user.id,
                category='Food'
            )
            assert result['success'] == True
            assert len(result['expenses']) == 1
            assert result['expenses'][0]['category'] == 'Food'
    
    def test_list_expenses_by_month(self, app, test_user, test_expenses):
        """Filtering by month should work."""
        with app.app_context():
            today = date.today()
            month = f"{today.year}-{today.month:02d}"
            result = ExpenseService.list_expenses(
                user_id=test_user.id,
                month=month
            )
            assert result['success'] == True
            # Should include at least some expenses from this month
    
    def test_get_today_total(self, app, test_user, test_expenses):
        """Getting today's total should work."""
        with app.app_context():
            result = ExpenseService.get_today_total(test_user.id)
            # Returns float directly, not dict
            assert isinstance(result, (int, float))
            assert result == 50.00  # Only first expense is today
    
    def test_get_month_total(self, app, test_user, test_expenses):
        """Getting month total should work."""
        with app.app_context():
            result = ExpenseService.get_month_total(test_user.id)
            # Returns float directly
            assert isinstance(result, (int, float))
            assert result == 105.00  # All 3 expenses are this month
    
    def test_get_category_breakdown(self, app, test_user, test_expenses):
        """Getting category breakdown should work."""
        with app.app_context():
            result = ExpenseService.get_category_breakdown(test_user.id)
            # Returns dict directly mapping category to amount
            assert isinstance(result, dict)
            assert 'Food' in result
            assert 'Transport' in result
            assert 'Entertainment' in result
    
    def test_export_to_csv(self, app, test_user, test_expenses):
        """Exporting to CSV should work."""
        with app.app_context():
            result = ExpenseService.export_to_csv(
                user_id=test_user.id,
                filters={}
            )
            assert 'id,date,title' in result  # CSV header
            assert 'Groceries' in result


# ============ BUDGET SERVICE TESTS ============

class TestBudgetService:
    """Test BudgetService methods."""
    
    def test_set_budget_valid(self, app, test_user):
        """Setting valid budget should succeed."""
        with app.app_context():
            result = BudgetService.set_budget(
                user_id=test_user.id,
                budget_amount=1000.00
            )
            assert result['success'] == True
            assert result['budget'] == 1000.00
    
    def test_set_budget_negative(self, app, test_user):
        """Setting negative budget should fail."""
        with app.app_context():
            with pytest.raises(ValueError):
                BudgetService.set_budget(
                    user_id=test_user.id,
                    budget_amount=-100
                )
    
    def test_get_budget_no_set(self, app, test_user):
        """Getting budget when not set should return None."""
        with app.app_context():
            result = BudgetService.get_budget(test_user.id)
            assert result['success'] == True
            assert result['budget'] is None
    
    def test_get_budget_with_spending(self, app, test_user_with_budget, test_expenses):
        """Getting budget with spending should show correct values."""
        with app.app_context():
            result = BudgetService.get_budget(test_user_with_budget.id)
            assert result['success'] == True
            assert result['budget'] == 1000.00
            assert result['month_spent'] == 105.00
            assert result['remaining'] == 895.00
            assert result['is_exceeded'] == False
    
    def test_check_budget_exceeds_threshold(self, app, test_user, test_expenses):
        """Checking budget threshold should work."""
        with app.app_context():
            # Set budget to 100, spending is 105
            BudgetService.set_budget(test_user.id, 100.00)
            
            result = BudgetService.check_budget_exceeds(test_user.id, threshold_percent=80)
            assert result['success'] == True
            assert result['alert_type'] == 'danger'
    
    def test_get_budget_status_ok(self, app, test_user_with_budget):
        """Getting budget status when ok should show ok."""
        with app.app_context():
            result = BudgetService.get_budget_status(test_user_with_budget.id)
            assert result['success'] == True
            assert result['status'] == 'ok'
    
    def test_create_budget_alert_danger(self, app, test_user, test_expenses):
        """Creating danger alert should work."""
        with app.app_context():
            BudgetService.set_budget(test_user.id, 100.00)  # Spending exceeds this
            
            result = BudgetService.create_budget_alert(
                test_user.id,
                alert_type='danger',
                percentage_used=105
            )
            assert result['success'] == True
            assert result['alert_created'] == True


# ============ REPOSITORY TESTS ============

class TestRepositories:
    """Test repository layer."""
    
    def test_user_repo_get_by_username(self, app, test_user):
        """Getting user by username should work."""
        with app.app_context():
            user = user_repo.get_by_username('testuser')
            assert user is not None
            assert user.username == 'testuser'
    
    def test_user_repo_username_exists(self, app, test_user):
        """Checking username existence should work."""
        with app.app_context():
            assert user_repo.username_exists('testuser') == True
            assert user_repo.username_exists('nonexistent') == False
    
    def test_expense_repo_get_user_expenses(self, app, test_user, test_expenses):
        """Getting user expenses should work."""
        with app.app_context():
            expenses = expense_repo.get_user_expenses(test_user.id)
            assert len(expenses) == 3
    
    def test_expense_repo_get_by_category(self, app, test_user, test_expenses):
        """Getting expenses by category should work."""
        with app.app_context():
            expenses = expense_repo.get_user_expenses_by_category(test_user.id, 'Food')
            assert len(expenses) == 1
            assert expenses[0].category == 'Food'
    
    def test_expense_repo_month_total(self, app, test_user, test_expenses):
        """Getting month total should work."""
        with app.app_context():
            today = date.today()
            total = expense_repo.get_month_total(test_user.id, today.year, today.month)
            assert total == 105.00
    
    def test_setting_repo_get_setting_value(self, app, test_user_with_budget):
        """Getting setting value should work."""
        with app.app_context():
            value = setting_repo.get_setting_value(
                test_user_with_budget.id,
                'monthly_budget'
            )
            assert value == '1000'
    
    def test_setting_repo_set_setting(self, app, test_user):
        """Setting a value should work."""
        with app.app_context():
            setting = setting_repo.set_setting(
                test_user.id,
                'currency',
                'USD'
            )
            assert setting.value == 'USD'


# ============ INTEGRATION TESTS ============

class TestIntegration:
    """Integration tests across services."""
    
    def test_full_expense_workflow(self, app, test_user):
        """Complete expense workflow should work."""
        with app.app_context():
            # Create expense
            create_result = ExpenseService.create_expense(
                user_id=test_user.id,
                title='Lunch',
                category='Food',
                amount=15.00,
                date_obj=date.today()
            )
            assert create_result['success'] == True
            expense_id = create_result['expense']['id']
            
            # Update expense
            update_result = ExpenseService.update_expense(
                user_id=test_user.id,
                expense_id=expense_id,
                amount=20.00
            )
            assert update_result['success'] == True
            assert update_result['expense']['amount'] == 20.00
            
            # Delete expense
            delete_result = ExpenseService.delete_expense(
                user_id=test_user.id,
                expense_id=expense_id
            )
            assert delete_result['success'] == True
    
    def test_budget_and_expense_workflow(self, app, test_user):
        """Budget and expense in tandem should work."""
        with app.app_context():
            # Set budget
            BudgetService.set_budget(test_user.id, 100.00)
            
            # Add expenses up to budget
            ExpenseService.create_expense(
                user_id=test_user.id,
                title='Expense 1',
                category='Food',
                amount=50.00,
                date_obj=date.today()
            )
            
            # Check budget status
            budget_result = BudgetService.get_budget(test_user.id)
            assert budget_result['success'] == True
            assert budget_result['month_spent'] == 50.00
            assert budget_result['remaining'] == 50.00
            
            # Add more expenses
            ExpenseService.create_expense(
                user_id=test_user.id,
                title='Expense 2',
                category='Transport',
                amount=60.00,
                date_obj=date.today()
            )
            
            # Check that budget is exceeded
            budget_result = BudgetService.get_budget(test_user.id)
            assert budget_result['month_spent'] == 110.00
            assert budget_result['is_exceeded'] == True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
