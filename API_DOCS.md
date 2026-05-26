# Expense Tracker API Documentation

This document describes the JWT-authenticated REST API endpoints for the Expense Tracker application.

## Authentication

All API endpoints (except `/api/auth/register` and `/api/auth/login`) require a valid JWT token to be passed in the `Authorization` header:

```
Authorization: Bearer <token>
```

### Register User
**POST** `/api/auth/register`

Request body:
```json
{
  "username": "user@example.com",
  "password": "securepassword"
}
```

Response (201):
```json
{
  "message": "User created successfully"
}
```

### Login
**POST** `/api/auth/login`

Request body:
```json
{
  "username": "user@example.com",
  "password": "securepassword"
}
```

Response (200):
```json
{
  "token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "user@example.com"
  }
}
```

## Expenses Endpoints

### Get All Expenses
**GET** `/api/expenses`

Response (200):
```json
[
  {
    "id": 1,
    "date": "2026-01-25",
    "title": "Coffee",
    "category": "Food",
    "amount": 5.50,
    "description": "Morning coffee"
  },
  ...
]
```

### Create Expense
**POST** `/api/expenses`

Request body:
```json
{
  "date": "2026-01-25",
  "title": "Lunch",
  "category": "Food",
  "amount": 12.99,
  "description": "Lunch with colleague"
}
```

Response (201):
```json
{
  "id": 2,
  "message": "Expense created successfully"
}
```

### Get Specific Expense
**GET** `/api/expenses/<expense_id>`

Response (200):
```json
{
  "id": 1,
  "date": "2026-01-25",
  "title": "Coffee",
  "category": "Food",
  "amount": 5.50,
  "description": "Morning coffee"
}
```

### Update Expense
**PUT** `/api/expenses/<expense_id>`

Request body (all fields optional):
```json
{
  "date": "2026-01-26",
  "title": "Updated Coffee",
  "category": "Beverages",
  "amount": 6.00,
  "description": "Updated description"
}
```

Response (200):
```json
{
  "message": "Expense updated successfully"
}
```

### Delete Expense
**DELETE** `/api/expenses/<expense_id>`

Response (200):
```json
{
  "message": "Expense deleted successfully"
}
```

## Dashboard Endpoints

### Get Dashboard Statistics
**GET** `/api/dashboard/stats`

Response (200):
```json
{
  "today_total": 5.50,
  "month_total": 150.00,
  "budget": 2000.00,
  "budget_warning": false,
  "remaining_budget": 1850.00
}
```

## Error Responses

All error responses follow this format:

```json
{
  "message": "Error description"
}
```

Common HTTP status codes:
- **400**: Bad Request - Invalid input or missing required fields
- **401**: Unauthorized - Invalid or missing token
- **403**: Forbidden - User doesn't have permission to access this resource
- **404**: Not Found - Resource not found

## Example Usage

```bash
# Register
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "password123"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "user@example.com", "password": "password123"}'

# Get expenses (use token from login)
curl -X GET http://localhost:5000/api/expenses \
  -H "Authorization: Bearer <token>"

# Create expense
curl -X POST http://localhost:5000/api/expenses \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"date": "2026-01-25", "title": "Coffee", "category": "Food", "amount": 5.50}'

# Get dashboard stats
curl -X GET http://localhost:5000/api/dashboard/stats \
  -H "Authorization: Bearer <token>"
```

## Token Expiration

JWT tokens expire after 24 hours. After expiration, users need to log in again to get a new token.
