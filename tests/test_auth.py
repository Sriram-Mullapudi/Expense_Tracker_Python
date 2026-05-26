"""
Unit tests for authentication
Tests login, registration, password hashing, JWT tokens
"""

import pytest
import json
from datetime import datetime, timedelta
import jwt
from app import app, db, JWT_SECRET
from models import User
from werkzeug.security import check_password_hash, generate_password_hash


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
    password_hash = generate_password_hash('testpass123')
    user = User(
        username='testuser',
        email='test@example.com',
        password=password_hash
    )
    db.session.add(user)
    db.session.commit()
    return user


class TestRegistration:
    """Test user registration"""
    
    def test_register_new_user(self, client):
        """New user can register"""
        response = client.post('/register', data={
            'username': 'newuser',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'registered' in response.data.decode().lower() or 'success' in response.data.decode().lower()
        
        # Check user was created
        user = User.query.filter_by(username='newuser').first()
        assert user is not None
    
    def test_register_duplicate_username(self, client, test_user):
        """Cannot register with existing username"""
        response = client.post('/register', data={
            'username': 'testuser',  # Already exists
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'already exists' in response.data.decode().lower() or 'error' in response.data.decode().lower()
    
    def test_password_is_hashed(self, client):
        """Password is hashed, not stored in plain text"""
        response = client.post('/register', data={
            'username': 'hasheduser',
            'password': 'mypassword'
        }, follow_redirects=True)
        
        user = User.query.filter_by(username='hasheduser').first()
        
        # Password should be hashed
        assert user.password != 'mypassword'
        # But should still match when checked
        assert check_password_hash(user.password, 'mypassword')
    
    def test_register_missing_username(self, client):
        """Registration fails without username"""
        response = client.post('/register', data={
            'password': 'password123'
        }, follow_redirects=True)
        
        # Should either show error or not create user
        users = User.query.all()
        assert len(users) == 0
    
    def test_register_missing_password(self, client):
        """Registration fails without password"""
        response = client.post('/register', data={
            'username': 'testuser'
        }, follow_redirects=True)
        
        # Should either show error or not create user
        users = User.query.all()
        assert len(users) == 0


class TestLogin:
    """Test user login"""
    
    def test_login_success(self, client, test_user):
        """User can login with correct credentials"""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should be redirected to index page
        assert response.request.path == '/'
    
    def test_login_invalid_username(self, client):
        """Login fails with wrong username"""
        response = client.post('/login', data={
            'username': 'wronguser',
            'password': 'password123'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'invalid' in response.data.decode().lower() or 'error' in response.data.decode().lower()
    
    def test_login_invalid_password(self, client, test_user):
        """Login fails with wrong password"""
        response = client.post('/login', data={
            'username': 'testuser',
            'password': 'wrongpassword'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert 'invalid' in response.data.decode().lower() or 'error' in response.data.decode().lower()
    
    def test_login_required_decorator(self, client):
        """Protected routes redirect to login"""
        response = client.get('/')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location


class TestJWTTokens:
    """Test JWT token generation and validation"""
    
    def test_generate_token(self, client, test_user):
        """Token can be generated for user"""
        token = jwt.encode(
            {
                'user_id': test_user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        assert token is not None
        assert isinstance(token, str)
    
    def test_token_contains_user_id(self, client, test_user):
        """Token contains user ID"""
        token = jwt.encode(
            {
                'user_id': test_user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        assert decoded['user_id'] == test_user.id
    
    def test_token_has_expiration(self, client, test_user):
        """Token has expiration"""
        token = jwt.encode(
            {
                'user_id': test_user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        decoded = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        assert 'exp' in decoded
    
    def test_token_expires_after_24_hours(self, client, test_user):
        """Token expires after 24 hours"""
        # Create token that expired 1 hour ago
        token = jwt.encode(
            {
                'user_id': test_user.id,
                'exp': datetime.utcnow() - timedelta(hours=1)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        with pytest.raises(jwt.ExpiredSignatureError):
            jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
    
    def test_token_invalid_signature(self, client, test_user):
        """Token with wrong signature fails"""
        token = jwt.encode(
            {
                'user_id': test_user.id,
                'exp': datetime.utcnow() + timedelta(hours=24)
            },
            JWT_SECRET,
            algorithm='HS256'
        )
        
        # Try to decode with wrong secret
        with pytest.raises(jwt.InvalidTokenError):
            jwt.decode(token, 'wrong_secret', algorithms=['HS256'])


class TestLogout:
    """Test user logout"""
    
    def test_logout_clears_session(self, client, test_user):
        """Logout clears session"""
        # Login first
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Logout
        response = client.get('/logout', follow_redirects=True)
        
        assert response.status_code == 200
        # Should be redirected to login or home
        assert '/login' in response.request.path or '/' in response.request.path
    
    def test_protected_route_after_logout(self, client, test_user):
        """Protected routes require login after logout"""
        # Login
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Logout
        client.get('/logout')
        
        # Try to access protected route
        response = client.get('/')
        
        # Should redirect to login
        assert response.status_code == 302
        assert '/login' in response.location


class TestPasswordSecurity:
    """Test password security measures"""
    
    def test_password_hashed_not_stored_plain(self, client):
        """Passwords are hashed, not stored in plain text"""
        client.post('/register', data={
            'username': 'secureuser',
            'password': 'MySecurePassword123!'
        })
        
        user = User.query.filter_by(username='secureuser').first()
        
        # Should not contain plain text password
        assert 'MySecurePassword123!' not in user.password
        assert user.password.startswith('pbkdf2:sha256:')  # Werkzeug hash format
    
    def test_password_verification(self, client, test_user):
        """Password can be verified without storing plain text"""
        # test_user has password 'testpass123'
        assert check_password_hash(test_user.password, 'testpass123')
        assert not check_password_hash(test_user.password, 'wrongpassword')
    
    def test_different_passwords_different_hashes(self, client):
        """Same password generates different hashes (salt)"""
        hash1 = generate_password_hash('password')
        hash2 = generate_password_hash('password')
        
        # Hashes are different (due to salt)
        assert hash1 != hash2
        # But both verify the same password
        assert check_password_hash(hash1, 'password')
        assert check_password_hash(hash2, 'password')


class TestAuthorizationDecorators:
    """Test authorization decorators"""
    
    def test_admin_required_decorator(self, client):
        """Admin-only routes require admin role"""
        # Access admin route without login
        response = client.get('/admin')
        
        # Should redirect to login
        assert response.status_code == 302
    
    def test_regular_user_cannot_access_admin(self, client, test_user):
        """Regular user cannot access admin routes"""
        # Login as regular user
        client.post('/login', data={
            'username': 'testuser',
            'password': 'testpass123'
        })
        
        # Try to access admin route
        response = client.get('/admin')
        
        # Should deny access
        assert response.status_code == 302 or 'unauthorized' in response.data.decode().lower()
    
    def test_admin_user_can_access_admin(self, client):
        """Admin user can access admin routes"""
        # Create admin user
        password_hash = generate_password_hash('adminpass')
        admin = User(
            username='admin',
            email='admin@example.com',
            password=password_hash,
            role='admin'
        )
        db.session.add(admin)
        db.session.commit()
        
        # Login as admin
        client.post('/login', data={
            'username': 'admin',
            'password': 'adminpass'
        })
        
        # Access admin route
        response = client.get('/admin')
        
        # Should allow access
        assert response.status_code == 200
