"""Pydantic schemas for data validation and serialization."""

from typing import Optional, List
from datetime import datetime, date
from enum import Enum
from decimal import Decimal
from pydantic import BaseModel, Field, EmailStr, field_validator, ConfigDict
import re


class ExpenseCategory(str, Enum):
    """Valid expense categories."""
    FOOD = "food"
    TRANSPORT = "transport"
    UTILITIES = "utilities"
    ENTERTAINMENT = "entertainment"
    HEALTHCARE = "healthcare"
    SHOPPING = "shopping"
    BILLS = "bills"
    RENT = "rent"
    INSURANCE = "insurance"
    OTHER = "other"


class AlertFrequency(str, Enum):
    """Alert notification frequency."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    NEVER = "never"


# ============================================================================
# Expense Schemas
# ============================================================================

class ExpenseCreate(BaseModel):
    """Schema for creating a new expense."""
    
    title: str = Field(..., min_length=1, max_length=200, description="Expense title")
    amount: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="Expense amount")
    category: ExpenseCategory = Field(..., description="Expense category")
    description: Optional[str] = Field(None, max_length=500, description="Optional description")
    date: Optional[date] = Field(default_factory=date.today, description="Expense date")
    receipt_url: Optional[str] = Field(None, max_length=500, description="Receipt file path")
    
    @field_validator('title')
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Validate title is not empty after stripping."""
        v = v.strip()
        if not v:
            raise ValueError('Title cannot be empty')
        return v
    
    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, v) -> Decimal:
        """Ensure amount is Decimal and positive."""
        if isinstance(v, (int, float, str)):
            try:
                v = Decimal(str(v))
            except:
                raise ValueError('Amount must be a valid number')
        
        if v <= 0:
            raise ValueError('Amount must be greater than zero')
        
        if v > Decimal('999999999.99'):
            raise ValueError('Amount exceeds maximum limit')
        
        return v
    
    @field_validator('description')
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description format."""
        if v is None:
            return v
        
        v = v.strip()
        if not v:
            return None
        
        if len(v) > 500:
            raise ValueError('Description must be 500 characters or less')
        
        return v
    
    model_config = ConfigDict(use_enum_values=True)


class ExpenseUpdate(BaseModel):
    """Schema for updating an expense."""
    
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    amount: Optional[Decimal] = Field(None, gt=0, max_digits=12, decimal_places=2)
    category: Optional[ExpenseCategory] = None
    description: Optional[str] = Field(None, max_length=500)
    date: Optional[date] = None
    
    @field_validator('amount', mode='before')
    @classmethod
    def validate_amount(cls, v: Optional) -> Optional[Decimal]:
        """Validate amount if provided."""
        if v is None:
            return v
        
        if isinstance(v, (int, float, str)):
            try:
                v = Decimal(str(v))
            except:
                raise ValueError('Amount must be a valid number')
        
        if v <= 0:
            raise ValueError('Amount must be positive')
        
        return v
    
    model_config = ConfigDict(use_enum_values=True)


class ExpenseResponse(BaseModel):
    """Schema for expense response."""
    
    id: int
    title: str
    amount: Decimal
    category: str
    description: Optional[str]
    date: date
    user_id: int
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# User & Authentication Schemas
# ============================================================================

class UserRegister(BaseModel):
    """Schema for user registration."""
    
    username: str = Field(
        ...,
        min_length=3,
        max_length=80,
        description="Username (alphanumeric, underscore, hyphen)"
    )
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Strong password (min 8 chars)"
    )
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain letters, numbers, underscore, and hyphen')
        
        # Check for reserved usernames
        reserved = {'admin', 'root', 'system', 'api', 'app', 'test', 'user'}
        if v.lower() in reserved:
            raise ValueError(f'Username "{v}" is reserved')
        
        return v.strip()
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password complexity."""
        errors = []
        
        if len(v) < 8:
            errors.append('Password must be at least 8 characters')
        
        if not any(c.isupper() for c in v):
            errors.append('Password must contain at least one uppercase letter')
        
        if not any(c.islower() for c in v):
            errors.append('Password must contain at least one lowercase letter')
        
        if not any(c.isdigit() for c in v):
            errors.append('Password must contain at least one digit')
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            errors.append('Password must contain at least one special character')
        
        if errors:
            raise ValueError(' | '.join(errors))
        
        return v


class UserLogin(BaseModel):
    """Schema for user login."""
    
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    """Schema for user response."""
    
    id: int
    username: str
    email: str
    created_at: datetime
    two_fa_enabled: bool = False
    
    model_config = ConfigDict(from_attributes=True)


class PasswordChange(BaseModel):
    """Schema for changing password."""
    
    current_password: str = Field(..., description="Current password for verification")
    new_password: str = Field(
        ...,
        min_length=12,
        max_length=255,
        description="New password (must meet complexity requirements)"
    )
    confirm_password: str = Field(..., description="Confirmation of new password")
    
    @field_validator('new_password')
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        """Validate new password strength (production requirements)."""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must contain special character')
        return v
    
    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v: str, info) -> str:
        """Ensure passwords match."""
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v


# ============================================================================
# Budget Alert Schemas
# ============================================================================

class AlertCreate(BaseModel):
    """Schema for creating a budget alert."""
    
    category: Optional[ExpenseCategory] = Field(None, description="Alert for specific category or None for all")
    threshold: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2, description="Alert threshold amount")
    frequency: AlertFrequency = Field(default=AlertFrequency.MONTHLY, description="How often to check")
    enabled: bool = Field(default=True, description="Whether alert is active")
    
    @field_validator('threshold', mode='before')
    @classmethod
    def validate_threshold(cls, v) -> Decimal:
        """Validate threshold amount."""
        if isinstance(v, (int, float, str)):
            try:
                v = Decimal(str(v))
            except:
                raise ValueError('Threshold must be a valid number')
        
        if v <= 0:
            raise ValueError('Threshold must be greater than zero')
        
        return v


class AlertResponse(BaseModel):
    """Schema for alert response."""
    
    id: int
    category: Optional[str]
    threshold: float
    frequency: str
    enabled: bool
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================================
# Batch Validation
# ============================================================================

class BatchExpenseCreate(BaseModel):
    """Schema for creating multiple expenses."""
    
    expenses: List[ExpenseCreate] = Field(..., min_items=1, max_items=100)
    
    class Config:
        json_schema_extra = {
            "example": {
                "expenses": [
                    {
                        "amount": 25.50,
                        "category": "food",
                        "description": "Lunch"
                    },
                    {
                        "amount": 15.00,
                        "category": "transport",
                        "description": "Taxi"
                    }
                ]
            }
        }


# ============================================================================
# Error Response Schemas
# ============================================================================

class ErrorDetail(BaseModel):
    """Schema for validation error details."""
    
    field: str = Field(..., description="Field that failed validation")
    message: str = Field(..., description="Error message")


class ErrorResponse(BaseModel):
    """Schema for error response."""
    
    error: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
    details: Optional[List[ErrorDetail]] = Field(None, description="Detailed error information")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# Pagination Schemas
# ============================================================================

class PaginationParams(BaseModel):
    """Schema for pagination parameters."""
    
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=20, ge=1, le=100, description="Items per page")
    
    @field_validator('per_page')
    @classmethod
    def validate_per_page(cls, v: int) -> int:
        """Ensure per_page is reasonable."""
        if v > 100:
            return 100
        if v < 1:
            return 20
        return v


class PaginatedResponse(BaseModel):
    """Schema for paginated responses."""
    
    items: List[ExpenseResponse] = Field(..., description="Items in this page")
    total: int = Field(..., ge=0, description="Total items")
    page: int = Field(..., ge=1, description="Current page")
    per_page: int = Field(..., ge=1, description="Items per page")
    pages: int = Field(..., ge=0, description="Total pages")
    
    @property
    def has_next(self) -> bool:
        """Check if there's a next page."""
        return self.page < self.pages
    
    @property
    def has_prev(self) -> bool:
        """Check if there's a previous page."""
        return self.page > 1


# ============================================================================
# Analytics Schemas
# ============================================================================

class CategoryTotal(BaseModel):
    """Schema for category spending."""
    
    category: str = Field(..., description="Category name")
    total: float = Field(..., ge=0, description="Total spending in category")
    count: int = Field(..., ge=0, description="Number of expenses")


class AnalyticsResponse(BaseModel):
    """Schema for analytics data."""
    
    period: str = Field(..., description="Time period analyzed")
    total_spending: float = Field(..., ge=0, description="Total spending")
    expense_count: int = Field(..., ge=0, description="Number of expenses")
    average_expense: float = Field(..., ge=0, description="Average expense amount")
    by_category: List[CategoryTotal] = Field(..., description="Breakdown by category")
