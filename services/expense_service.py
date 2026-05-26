"""Expense service - pure business logic without Flask.

This service handles:
- Expense CRUD operations
- Expense filtering and retrieval
- Statistics calculation (daily, monthly, by category)
- Budget tracking

NO Flask imports. Returns clean Python dicts/lists for routes to format.
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal

from models import db, Expense, User, Alert


class ExpenseService:
    """Handles expense business logic."""
    
    @staticmethod
    def create_expense(
        user_id: int,
        title: str,
        category: str,
        amount: float,
        date_obj: date,
        description: Optional[str] = None,
        receipt_path: Optional[str] = None
    ) -> Dict:
        """
        Create a new expense.
        
        Args:
            user_id: Owner user ID
            title: Expense title (1-200 chars)
            category: Category name
            amount: Amount (positive, ≤999,999,999.99)
            date_obj: Expense date (not future)
            description: Optional description
            receipt_path: Optional receipt file path
        
        Returns:
            {"success": bool, "expense": {...}, "message": str}
        
        Raises:
            ValueError: If validation fails
        """
        # Validate user exists
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        
        # Validate inputs
        if not title or len(title) < 1 or len(title) > 200:
            raise ValueError('Title must be 1-200 characters')
        
        if not category or len(category) < 1:
            raise ValueError('Category is required')
        
        if amount <= 0 or amount > 999999999.99:
            raise ValueError('Amount must be positive and ≤ $999,999,999.99')
        
        if date_obj > date.today():
            raise ValueError('Expense date cannot be in the future')
        
        try:
            # Create expense
            expense = Expense(
                user_id=user_id,
                title=title.strip(),
                category=category.strip(),
                amount=Decimal(str(amount)),
                date=date_obj,
                description=description.strip() if description else None,
                receipt_path=receipt_path
            )
            db.session.add(expense)
            db.session.commit()
            
            return {
                'success': True,
                'expense': {
                    'id': expense.id,
                    'title': expense.title,
                    'category': expense.category,
                    'amount': float(expense.amount),
                    'date': expense.date.isoformat(),
                    'description': expense.description,
                    'receipt_path': expense.receipt_path,
                    'created_at': expense.created_at.isoformat()
                },
                'message': f"Expense '{title}' created successfully"
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Failed to create expense: {str(e)}')
    
    @staticmethod
    def update_expense(
        user_id: int,
        expense_id: int,
        title: Optional[str] = None,
        category: Optional[str] = None,
        amount: Optional[float] = None,
        date_obj: Optional[date] = None,
        description: Optional[str] = None
    ) -> Dict:
        """
        Update an existing expense.
        
        Args:
            user_id: Requesting user ID (must own expense)
            expense_id: Expense to update
            title: New title (optional)
            category: New category (optional)
            amount: New amount (optional)
            date_obj: New date (optional)
            description: New description (optional)
        
        Returns:
            {"success": bool, "expense": {...}, "message": str}
        """
        # Find expense and verify ownership
        expense = Expense.query.get(expense_id)
        if not expense or expense.user_id != user_id:
            raise ValueError('Expense not found or not authorized')
        
        try:
            # Update fields if provided
            if title is not None:
                if len(title) < 1 or len(title) > 200:
                    raise ValueError('Title must be 1-200 characters')
                expense.title = title.strip()
            
            if category is not None:
                if not category:
                    raise ValueError('Category cannot be empty')
                expense.category = category.strip()
            
            if amount is not None:
                if amount <= 0 or amount > 999999999.99:
                    raise ValueError('Amount must be positive and ≤ $999,999,999.99')
                expense.amount = Decimal(str(amount))
            
            if date_obj is not None:
                if date_obj > date.today():
                    raise ValueError('Expense date cannot be in the future')
                expense.date = date_obj
            
            if description is not None:
                expense.description = description.strip() if description else None
            
            db.session.commit()
            
            return {
                'success': True,
                'expense': {
                    'id': expense.id,
                    'title': expense.title,
                    'category': expense.category,
                    'amount': float(expense.amount),
                    'date': expense.date.isoformat(),
                    'description': expense.description,
                    'receipt_path': expense.receipt_path,
                    'created_at': expense.created_at.isoformat()
                },
                'message': 'Expense updated successfully'
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Failed to update expense: {str(e)}')
    
    @staticmethod
    def delete_expense(user_id: int, expense_id: int) -> Dict:
        """
        Delete an expense.
        
        Args:
            user_id: Requesting user ID (must own expense)
            expense_id: Expense to delete
        
        Returns:
            {"success": bool, "message": str}
        """
        # Find expense and verify ownership
        expense = Expense.query.get(expense_id)
        if not expense or expense.user_id != user_id:
            raise ValueError('Expense not found or not authorized')
        
        try:
            title = expense.title
            db.session.delete(expense)
            db.session.commit()
            
            return {
                'success': True,
                'message': f"Expense '{title}' deleted successfully"
            }
        
        except Exception as e:
            db.session.rollback()
            raise Exception(f'Failed to delete expense: {str(e)}')
    
    @staticmethod
    def get_expense(user_id: int, expense_id: int) -> Dict:
        """
        Get single expense details.
        
        Returns:
            {"success": bool, "expense": {...}}
        """
        expense = Expense.query.get(expense_id)
        if not expense or expense.user_id != user_id:
            raise ValueError('Expense not found or not authorized')
        
        return {
            'success': True,
            'expense': {
                'id': expense.id,
                'title': expense.title,
                'category': expense.category,
                'amount': float(expense.amount),
                'date': expense.date.isoformat(),
                'description': expense.description,
                'receipt_path': expense.receipt_path,
                'created_at': expense.created_at.isoformat()
            }
        }
    
    @staticmethod
    def list_expenses(
        user_id: int,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        category: Optional[str] = None,
        month: Optional[str] = None
    ) -> Dict:
        """
        List expenses with optional filters.
        
        Args:
            user_id: User ID
            date_from: Start date (optional)
            date_to: End date (optional)
            category: Filter by category (optional)
            month: Filter by month YYYY-MM (optional)
        
        Returns:
            {"success": bool, "expenses": [...], "total": float}
        """
        try:
            query = Expense.query.filter_by(user_id=user_id)
            
            # Apply month filter
            if month:
                try:
                    from datetime import datetime
                    month_date = datetime.strptime(month, '%Y-%m').date()
                    first_day = month_date.replace(day=1)
                    # Calculate last day of month
                    next_month = first_day + timedelta(days=32)
                    last_day = next_month.replace(day=1) - timedelta(days=1)
                    query = query.filter(Expense.date >= first_day, Expense.date <= last_day)
                except ValueError:
                    raise ValueError('Month must be in YYYY-MM format')
            
            # Apply date range filters
            if date_from:
                query = query.filter(Expense.date >= date_from)
            if date_to:
                query = query.filter(Expense.date <= date_to)
            
            # Apply category filter
            if category and category.lower() != 'all':
                query = query.filter_by(category=category)
            
            # Execute query and sort
            expenses = query.order_by(Expense.date.desc()).all()
            
            # Format response
            expense_list = [
                {
                    'id': e.id,
                    'title': e.title,
                    'category': e.category,
                    'amount': float(e.amount),
                    'date': e.date.isoformat(),
                    'description': e.description,
                    'receipt_path': e.receipt_path,
                    'created_at': e.created_at.isoformat()
                }
                for e in expenses
            ]
            
            total_spent = sum(float(e.amount) for e in expenses)
            
            return {
                'success': True,
                'expenses': expense_list,
                'total': total_spent,
                'count': len(expense_list)
            }
        
        except Exception as e:
            raise Exception(f'Failed to list expenses: {str(e)}')
    
    @staticmethod
    def get_today_total(user_id: int) -> float:
        """Get total expenses for today."""
        today = date.today()
        result = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.date == today
        ).scalar()
        return float(result) if result else 0.0
    
    @staticmethod
    def get_month_total(user_id: int, month: Optional[str] = None) -> float:
        """
        Get total expenses for a month.
        
        Args:
            user_id: User ID
            month: Month in YYYY-MM format (default: current month)
        """
        if month:
            try:
                from datetime import datetime
                month_date = datetime.strptime(month, '%Y-%m').date()
            except ValueError:
                raise ValueError('Month must be in YYYY-MM format')
        else:
            month_date = date.today()
        
        first_day = month_date.replace(day=1)
        next_month = first_day + timedelta(days=32)
        last_day = next_month.replace(day=1) - timedelta(days=1)
        
        result = db.session.query(db.func.sum(Expense.amount)).filter(
            Expense.user_id == user_id,
            Expense.date >= first_day,
            Expense.date <= last_day
        ).scalar()
        
        return float(result) if result else 0.0
    
    @staticmethod
    def get_category_breakdown(user_id: int, month: Optional[str] = None) -> Dict[str, float]:
        """
        Get spending breakdown by category.
        
        Returns:
            {"category1": amount1, "category2": amount2, ...}
        """
        query = db.session.query(
            Expense.category,
            db.func.sum(Expense.amount)
        ).filter_by(user_id=user_id)
        
        # Filter by month if provided
        if month:
            try:
                from datetime import datetime
                month_date = datetime.strptime(month, '%Y-%m').date()
            except ValueError:
                raise ValueError('Month must be in YYYY-MM format')
            
            first_day = month_date.replace(day=1)
            next_month = first_day + timedelta(days=32)
            last_day = next_month.replace(day=1) - timedelta(days=1)
            
            query = query.filter(
                Expense.date >= first_day,
                Expense.date <= last_day
            )
        
        results = query.group_by(Expense.category).all()
        
        return {
            category: float(amount)
            for category, amount in results
            if category
        }
    
    @staticmethod
    def export_to_csv(user_id: int, filters: Dict) -> str:
        """
        Export expenses to CSV format.
        
        Returns:
            CSV string (rows)
        """
        try:
            # Get filtered expenses
            result = ExpenseService.list_expenses(
                user_id,
                date_from=filters.get('date_from'),
                date_to=filters.get('date_to'),
                category=filters.get('category'),
                month=filters.get('month')
            )
            
            expenses = result['expenses']
            
            # Build CSV
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['id', 'date', 'title', 'category', 'amount', 'description'])
            
            for expense in expenses:
                writer.writerow([
                    expense['id'],
                    expense['date'],
                    expense['title'],
                    expense['category'],
                    f"{expense['amount']:.2f}",
                    expense['description'] or ''
                ])
            
            return output.getvalue()
        
        except Exception as e:
            raise Exception(f'Failed to export expenses: {str(e)}')
