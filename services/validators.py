"""Service layer validation schemas using Pydantic.

These schemas define the input/output contracts for all services.
They handle validation WITHOUT any Flask dependency.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from datetime import date as date_type, datetime


# ============ AUTH VALIDATION ============

class LoginRequest(BaseModel):
    """Validate login request data."""
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=1)
    remember: bool = False
    
    @validator('username')
    def validate_username(cls, v):
        """Ensure username contains valid characters."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric (with _ and - allowed)')
        return v.strip().lower()


class RegisterRequest(BaseModel):
    """Validate registration request data."""
    username: str = Field(..., min_length=3, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=12)  # Tier 1 requirement: 12+ chars
    confirm_password: str
    
    @validator('username')
    def validate_username(cls, v):
        """Ensure username valid."""
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must be alphanumeric')
        return v.strip().lower()
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Enforce strong password requirements (Tier 1)."""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must include uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must include lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must include digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must include special character')
        return v
    
    @validator('confirm_password')
    def passwords_match(cls, v, values):
        """Ensure passwords match."""
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v


class ForgotPasswordRequest(BaseModel):
    """Validate forgot password request."""
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Validate password reset request."""
    token: str
    password: str = Field(..., min_length=12)
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Enforce strong password."""
        if not any(c.isupper() for c in v):
            raise ValueError('Password must include uppercase')
        if not any(c.islower() for c in v):
            raise ValueError('Password must include lowercase')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must include digit')
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in v):
            raise ValueError('Password must include special character')
        return v


class UserResponse(BaseModel):
    """Response data for user information."""
    id: int
    username: str
    email: str
    role: str
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True  # SQLAlchemy ORM compatibility


class AuthResponse(BaseModel):
    """Response data after successful auth operation."""
    success: bool
    user: UserResponse
    message: str


# ============ EXPENSE VALIDATION ============

class ExpenseCreateRequest(BaseModel):
    """Validate expense creation."""
    title: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1, max_length=50)
    amount: float = Field(..., gt=0, le=999999999.99)
    description: Optional[str] = Field(None, max_length=500)
    date: date_type = Field(...)
    
    @validator('date')
    def validate_date_not_future(cls, v):
        """Ensure date is not in future."""
        if v > date_type.today():
            raise ValueError('Expense date cannot be in the future')
        return v


class ExpenseUpdateRequest(BaseModel):
    """Validate expense update."""
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    category: Optional[str] = Field(None, min_length=1, max_length=50)
    amount: Optional[float] = Field(None, gt=0, le=999999999.99)
    description: Optional[str] = Field(None, max_length=500)
    date: Optional[date_type] = None
    
    @validator('date')
    def validate_date_not_future(cls, v):
        """Date must not be future."""
        if v and v > date_type.today():
            raise ValueError('Expense date cannot be in the future')
        return v


class ExpenseResponse(BaseModel):
    """Response data for expense."""
    id: int
    user_id: int
    date: date_type
    title: str
    category: str
    amount: float
    description: Optional[str]
    receipt_path: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ EXPENSE FILTERING ============

class ExpenseFilterRequest(BaseModel):
    """Validate expense filtering parameters."""
    date_from: Optional[date_type] = None
    date_to: Optional[date_type] = None
    category: Optional[str] = None
    month: Optional[str] = None  # YYYY-MM format
    
    @validator('date_from', 'date_to')
    def validate_dates_not_future(cls, v):
        """Dates must not be in future."""
        if v and v > date_type.today():
            raise ValueError('Filter date cannot be in the future')
        return v
    
    @validator('date_to')
    def validate_date_range(cls, v, values):
        """Ensure date_to >= date_from."""
        if v and 'date_from' in values and values['date_from']:
            if v < values['date_from']:
                raise ValueError('End date must be after start date')
        return v
    
    @validator('month')
    def validate_month_format(cls, v):
        """Validate YYYY-MM format."""
        if v:
            from datetime import datetime
            try:
                datetime.strptime(v, '%Y-%m')
            except ValueError:
                raise ValueError('Month must be in YYYY-MM format')
        return v


class ExpenseStatsResponse(BaseModel):
    """Response data for expense statistics."""
    total_spent: float
    today_total: float
    month_total: float
    budget: float
    budget_warning: bool
    remaining_budget: float


class CategoryBreakdownResponse(BaseModel):
    """Response data for category breakdown."""
    category: str
    amount: float
    percentage: float


# ============ SETTINGS VALIDATION ============

class SettingUpdateRequest(BaseModel):
    """Validate settings update."""
    monthly_budget: Optional[float] = Field(None, ge=0)
    currency: Optional[str] = None
    
    @validator('monthly_budget')
    def validate_budget(cls, v):
        """Budget must be reasonable."""
        if v is not None and v > 999999999.99:
            raise ValueError('Budget amount too large')
        return v


# ============ BUDGET VALIDATION ============

class BudgetSetRequest(BaseModel):
    """Validate budget setting."""
    budget_amount: float = Field(..., gt=0, le=999999999.99)
    
    @validator('budget_amount')
    def validate_amount(cls, v):
        """Ensure amount is reasonable."""
        if v <= 0:
            raise ValueError('Budget must be greater than 0')
        if v > 999999999.99:
            raise ValueError('Budget cannot exceed $999,999,999.99')
        return float(v)


class BudgetStatusResponse(BaseModel):
    """Response data for budget status."""
    budget_set: bool
    budget: Optional[float] = None
    spent: float
    remaining: Optional[float] = None
    percentage: float
    status: str  # "ok", "warning", "exceeded"
    message: str


class BudgetAlertRequest(BaseModel):
    """Validate budget alert creation."""
    alert_type: str  # "warning" or "danger"
    percentage_used: float = Field(..., ge=0)
    
    @validator('alert_type')
    def validate_alert_type(cls, v):
        """Alert type must be valid."""
        if v not in ['warning', 'danger']:
            raise ValueError('Alert type must be warning or danger')
        return v
    
    @validator('percentage_used')
    def validate_percentage(cls, v):
        """Percentage must be valid."""
        if v < 0:
            raise ValueError('Percentage cannot be negative')
        return v
