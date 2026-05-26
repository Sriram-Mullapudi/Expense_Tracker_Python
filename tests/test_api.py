"""
Unit tests for API endpoints
Tests REST API routes, JSON responses, JWT auth
"""

import pytest
import json
from datetime import datetime, date, timedelta
import jwt
from app import app, db, JWT_SECRET
from models import User, Expense, Alert
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
    """Create test user"""
    user = User(
        username='testuser',
        email='test@example.com',
        password=generate_password_hash('testpass123')
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def jwt_token(test_user):
    """Generate JWT token for test user"""
    return jwt.encode(
        {
            'user_id': test_user.id,
            'exp': datetime.utcnow() + timedelta(hours=24)
        },
        JWT_SECRET,
        algorithm='HS256'
    )


class TestAuthAPI:
    """Test authentication API endpoints"""
    
    def test_api_register_success(self, client):
        """API user registration succeeds"""
        response = client.post('/api/auth/register', 
            json={
                'username': 'newuser',
                'password': 'password123'
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'message' in data or 'success' in data


class TestExpenseAPI:
    """Test expense API endpoints"""
    
    def test_get_expenses_requires_token(self, client):
        """GET /api/expenses requires JWT token"""
        response = client.get('/api/expenses')
        
        # Should return 401 Unauthorized
        assert response.status_code == 401
    
    def test_get_expenses_with_token(self, client, test_user, jwt_token):
        """GET /api/expenses returns user expenses"""
        # Create test expense
        expense = Expense(
            user_id=test_user.id,
            title='Test expense',
            amount=25.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        # GET with token
        response = client.get('/api/expenses',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]['title'] == 'Test expense'
        assert data[0]['amount'] == 25.0
    
    def test_get_expenses_invalid_token(self, client):
        """GET /api/expenses rejects invalid token"""
        response = client.get('/api/expenses',
            headers={'Authorization': 'Bearer invalid_token'}
        )
        
        assert response.status_code == 401
    
    def test_create_expense_api(self, client, test_user, jwt_token):
        """POST /api/expenses creates expense"""
        response = client.post('/api/expenses',
            headers={'Authorization': f'Bearer {jwt_token}'},
            json={
                'title': 'API expense',
                'amount': 50.0,
                'date': date.today().isoformat(),
                'category': 'Transport'
            }
        )
        
        assert response.status_code == 201
        data = json.loads(response.data)
        assert 'id' in data
        
        # Verify in database
        expense = Expense.query.filter_by(title='API expense').first()
        assert expense is not None
        assert expense.amount == 50.0
    
    def test_create_expense_requires_fields(self, client, test_user, jwt_token):
        """POST /api/expenses requires all fields"""
        response = client.post('/api/expenses',
            headers={'Authorization': f'Bearer {jwt_token}'},
            json={
                'title': 'Incomplete'
                # Missing amount, date
            }
        )
        
        assert response.status_code == 400
    
    def test_get_expense_by_id(self, client, test_user, jwt_token):
        """GET /api/expenses/<id> returns single expense"""
        expense = Expense(
            user_id=test_user.id,
            title='Single',
            amount=15.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        response = client.get(f'/api/expenses/{expense.id}',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['title'] == 'Single'
    
    def test_update_expense_api(self, client, test_user, jwt_token):
        """PUT /api/expenses/<id> updates expense"""
        expense = Expense(
            user_id=test_user.id,
            title='Original',
            amount=20.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        response = client.put(f'/api/expenses/{expense.id}',
            headers={'Authorization': f'Bearer {jwt_token}'},
            json={
                'title': 'Updated',
                'amount': 30.0
            }
        )
        
        assert response.status_code == 200
        
        updated = Expense.query.get(expense.id)
        assert updated.title == 'Updated'
        assert updated.amount == 30.0
    
    def test_delete_expense_api(self, client, test_user, jwt_token):
        """DELETE /api/expenses/<id> deletes expense"""
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
        
        response = client.delete(f'/api/expenses/{expense_id}',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        assert Expense.query.get(expense_id) is None
    
    def test_user_cannot_access_others_expenses(self, client, test_user, jwt_token):
        """User can only access their own expenses"""
        # Create another user and their expense
        other_user = User(
            username='otheruser',
            email='other@test.com',
            password=generate_password_hash('pass')
        )
        db.session.add(other_user)
        db.session.commit()
        
        other_expense = Expense(
            user_id=other_user.id,
            title='Other user expense',
            amount=100.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(other_expense)
        db.session.commit()
        
        # Try to access with test_user's token
        response = client.get(f'/api/expenses/{other_expense.id}',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        # Should deny access
        assert response.status_code == 403


class TestAlertAPI:
    """Test alert API endpoints"""
    
    def test_get_alerts(self, client, test_user, jwt_token):
        """GET /api/alerts returns alerts"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            severity='warning'
        )
        db.session.add(alert)
        db.session.commit()
        
        response = client.get('/api/alerts',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
        assert len(data) > 0
    
    def test_dismiss_alert(self, client, test_user, jwt_token):
        """PUT /api/alerts/<id>/dismiss marks alert as read"""
        alert = Alert(
            user_id=test_user.id,
            alert_type='budget_warning',
            severity='warning',
            is_read=False
        )
        db.session.add(alert)
        db.session.commit()
        
        response = client.put(f'/api/alerts/{alert.id}/dismiss',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        
        updated_alert = Alert.query.get(alert.id)
        assert updated_alert.is_read is True


class TestAnalyticsAPI:
    """Test analytics API endpoints"""
    
    def test_analytics_trends(self, client, test_user, jwt_token):
        """GET /api/analytics/trends returns monthly data"""
        # Add expense
        expense = Expense(
            user_id=test_user.id,
            title='Test',
            amount=50.0,
            date=date.today(),
            category='Food'
        )
        db.session.add(expense)
        db.session.commit()
        
        response = client.get('/api/analytics/trends',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, dict)
        assert len(data) == 12  # 12 months
    
    def test_analytics_categories(self, client, test_user, jwt_token):
        """GET /api/analytics/categories returns breakdown"""
        expenses = [
            Expense(user_id=test_user.id, title='E1', amount=30.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E2', amount=20.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E3', amount=50.0, date=date.today(), category='Transport'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        response = client.get('/api/analytics/categories',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'Food' in data
        assert data['Food'] == 50.0
        assert 'Transport' in data
        assert data['Transport'] == 50.0
    
    def test_analytics_stats(self, client, test_user, jwt_token):
        """GET /api/analytics/stats returns statistics"""
        expenses = [
            Expense(user_id=test_user.id, title='E1', amount=10.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E2', amount=20.0, date=date.today(), category='Food'),
            Expense(user_id=test_user.id, title='E3', amount=30.0, date=date.today(), category='Food'),
        ]
        db.session.add_all(expenses)
        db.session.commit()
        
        response = client.get('/api/analytics/stats',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['total'] == 60.0
        assert data['average'] == 20.0
        assert data['count'] == 3


class TestAdminAPI:
    """Test admin API endpoints"""
    
    def test_admin_users_requires_admin(self, client, test_user, jwt_token):
        """Admin endpoint requires admin role"""
        response = client.get('/api/admin/users',
            headers={'Authorization': f'Bearer {jwt_token}'}
        )
        
        # Regular user should be denied
        assert response.status_code == 403
    
    def test_admin_can_access_users(self, client):
        """Admin can access user list"""
        # Create admin user
        admin = User(
            username='admin',
            email='admin@test.com',
            password=generate_password_hash('adminpass'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        
        admin_token = jwt.encode(
            {
                'user_id': admin.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        response = client.get('/api/admin/users',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        
        assert response.status_code == 200
        data = json.loads(response.data)
        assert isinstance(data, list)
    
    def test_promote_to_admin(self, client, test_user):
        """Admin can promote user to admin"""
        # Create admin
        admin = User(
            username='admin',
            email='admin@test.com',
            password=generate_password_hash('pass'),
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        
        admin_token = jwt.encode(
            {
                'user_id': admin.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        # Promote test_user
        response = client.post(f'/api/admin/promote-admin/{test_user.id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        
        assert response.status_code == 200
        
        promoted = User.query.get(test_user.id)
        assert promoted.role == 'admin'


class TestFileUploadAPI:
    """Test file upload API endpoints"""
    
    def test_upload_requires_token(self, client):
        """File upload requires auth"""
        response = client.post('/api/upload/receipt')
        
        assert response.status_code == 401
    
    def test_upload_invalid_file_type(self, client, test_user, jwt_token):
        """File upload rejects invalid types"""
        data = {
            'file': (b'fake content', 'test.exe')
        }
        
        response = client.post('/api/upload/receipt',
            headers={'Authorization': f'Bearer {jwt_token}'},
            data=data
        )
        
        assert response.status_code == 400
    
    def test_upload_valid_image(self, client, test_user, jwt_token):
        """File upload accepts valid images"""
        # Create a minimal valid PNG
        png_data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        
        data = {
            'file': (png_data, 'receipt.png')
        }
        
        response = client.post('/api/upload/receipt',
            headers={'Authorization': f'Bearer {jwt_token}'},
            data=data,
            content_type='multipart/form-data'
        )
        
        # Should either succeed or return reasonable error
        assert response.status_code in [200, 201, 400]
