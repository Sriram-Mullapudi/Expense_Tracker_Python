"""Database models for Expense Tracker application."""
from typing import List, Optional
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, date as date_type, timezone
from decimal import Decimal
from sqlalchemy import CheckConstraint, UniqueConstraint, Index

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication and expense ownership.
    
    Attributes:
        id: Unique user identifier
        username: Unique username for login (3-80 chars)
        email: User email address for notifications
        password: Bcrypt-hashed password
        reset_token: Temporary token for password reset
        reset_token_expires: Expiration time for reset token
        role: User role ('user' or 'admin')
        created_at: Account creation timestamp
        expenses: Relationship to user's expenses
        settings: Relationship to user settings
        alerts: Relationship to user alerts
    """
    __allow_unmapped__ = True
    __table_args__ = (
        CheckConstraint('LENGTH(username) >= 3 AND LENGTH(username) <= 80', name='valid_username_length'),
        CheckConstraint('LENGTH(password) >= 60', name='valid_password_hash_length'),  # Bcrypt = 60 chars
    )
    
    id: int = db.Column(db.Integer, primary_key=True)
    username: str = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email: str = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password: str = db.Column(db.String(255), nullable=False)  # Allow for future hash algorithms
    reset_token: Optional[str] = db.Column(db.String(100), unique=True)
    reset_token_expires: Optional[datetime] = db.Column(db.DateTime)
    role: str = db.Column(db.String(20), default="user", nullable=False)  # user, admin
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationships
    expenses: List['Expense'] = db.relationship(
        'Expense', backref='user', lazy=True, cascade='all, delete-orphan'
    )
    settings: List['Setting'] = db.relationship(
        'Setting', backref='user', lazy=True, cascade='all, delete-orphan'
    )
    alerts: List['Alert'] = db.relationship(
        'Alert', backref='user', lazy=True, cascade='all, delete-orphan'
    )

    def __repr__(self) -> str:
        """Return string representation of User."""
        return f'<User {self.username} ({self.role})>'
    
    def is_admin(self) -> bool:
        """Check if user has admin role.
        
        Returns:
            True if user is admin, False otherwise
        """
        return self.role == 'admin'


class Expense(db.Model):
    """Expense model for tracking user expenses.
    
    Attributes:
        id: Unique expense identifier
        user_id: Foreign key reference to User
        date: Date when expense occurred
        title: Short description of expense
        category: Expense category (food, transport, utilities, etc)
        amount: Expense amount in Decimal (not float!) for financial accuracy
        description: Detailed description (optional)
        receipt_path: File path to receipt image/PDF (optional)
        created_at: Timestamp when record was created
        user: Relationship to User object
    """
    __allow_unmapped__ = True
    __table_args__ = (
        CheckConstraint('amount > 0', name='positive_amount'),
        CheckConstraint('LENGTH(title) > 0 AND LENGTH(title) <= 200', name='valid_title_length'),
        Index('idx_user_date', 'user_id', 'date'),  # Composite index for queries
        Index('idx_user_category_date', 'user_id', 'category', 'date'),  # For analytics
        Index('idx_created_at', 'created_at'),  # For audit logs
    )
    
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    date: date_type = db.Column(db.Date, nullable=False, index=True)
    title: str = db.Column(db.String(200), nullable=False)
    category: str = db.Column(db.String(50), nullable=False, index=True)
    amount: Decimal = db.Column(
        db.Numeric(12, 2),  # 12 digits total, 2 after decimal ($999,999,999.99 max)
        nullable=False
    )
    description: Optional[str] = db.Column(db.String(500))
    receipt_path: Optional[str] = db.Column(db.String(500))
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self) -> str:
        """Return string representation of Expense."""
        return f'<Expense {self.title} - ${self.amount}>'
    
    def validate(self) -> List[str]:
        """Validate expense data before save.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.title or len(self.title) == 0:
            errors.append('Title cannot be empty')
        if len(self.title) > 200:
            errors.append('Title must be <= 200 characters')
        
        if self.amount is None:
            errors.append('Amount is required')
        elif isinstance(self.amount, (int, float)):
            self.amount = Decimal(str(self.amount))
        
        if self.amount <= 0:
            errors.append('Amount must be greater than zero')
        
        if self.amount > Decimal('999999999.99'):
            errors.append('Amount exceeds maximum limit')
        
        return errors


class Setting(db.Model):
    """Settings model for user-specific configuration.
    
    Attributes:
        id: Unique setting identifier
        user_id: Foreign key reference to User
        key: Setting name/key (e.g., 'monthly_budget', 'currency')
        value: Setting value as string
        user: Relationship to User object
    """
    __allow_unmapped__ = True
    __table_args__ = (
        UniqueConstraint('user_id', 'key', name='unique_user_setting'),
    )
    
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    key: str = db.Column(db.String(50), nullable=False)
    value: Optional[str] = db.Column(db.String(500))

    def __repr__(self) -> str:
        """Return string representation of Setting."""
        return f'<Setting {self.key}={self.value}>'


class Alert(db.Model):
    """Alert model for budget warnings and notifications.
    
    Attributes:
        id: Unique alert identifier
        user_id: Foreign key reference to User
        alert_type: Type of alert (budget_warning, budget_exceeded, etc)
        title: Short alert title
        message: Detailed alert message
        severity: Alert severity level (warning, danger, info)
        is_read: Whether user has read the alert
        is_sent: Whether email notification has been sent
        created_at: Timestamp when alert was created
        triggered_month: Month that triggered the alert (YYYY-MM format)
        user: Relationship to User object
    """
    __allow_unmapped__ = True
    
    id: int = db.Column(db.Integer, primary_key=True)
    user_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    alert_type: str = db.Column(db.String(50), nullable=False)  # budget_warning, budget_exceeded, etc.
    title: str = db.Column(db.String(200), nullable=False)
    message: str = db.Column(db.String(500), nullable=False)
    severity: str = db.Column(db.String(20), default='warning')  # warning, danger, info
    is_read: bool = db.Column(db.Boolean, default=False, index=True)
    is_sent: bool = db.Column(db.Boolean, default=False, index=True)  # For email notifications
    created_at: datetime = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    triggered_month: Optional[str] = db.Column(db.String(7))  # YYYY-MM format

    def __repr__(self) -> str:
        """Return string representation of Alert."""
        return f'<Alert {self.title} - {self.alert_type}>'
