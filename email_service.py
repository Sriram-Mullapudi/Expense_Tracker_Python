"""Email service for sending notifications."""
from typing import Optional
from flask_mail import Mail, Message
from flask import render_template_string, current_app
from models import db, Alert, User, Expense
import os
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
mail = Mail()

# Email configuration validation
def is_email_configured() -> bool:
    """
    Check if email is properly configured.
    
    Returns:
        True if email server is configured with credentials, False otherwise
    """
    mail_server = current_app.config.get('MAIL_SERVER', 'localhost')
    # localhost or local SMTP servers won't work without actual service
    has_real_server = mail_server not in ['localhost', '127.0.0.1', 'localhost:25']
    has_credentials = current_app.config.get('MAIL_USERNAME') and current_app.config.get('MAIL_PASSWORD')
    
    return has_real_server or has_credentials


def send_email_with_fallback(msg: Message) -> bool:
    """
    Send email with fallback handling.
    
    Logs warnings/errors if email fails to send rather than raising exceptions.
    This allows the application to continue functioning without a configured email server.
    
    Args:
        msg: Flask-Mail Message object to send
    
    Returns:
        True if email sent successfully, False if failed (but logged)
    
    Raises:
        No exceptions - all errors are logged internally
    """
    try:
        # Check if email is configured
        if not is_email_configured():
            logger.warning(
                f"Email not configured for production. Set MAIL_SERVER, MAIL_USERNAME, "
                f"and MAIL_PASSWORD environment variables. "
                f"Email to {msg.recipients} would have been sent: {msg.subject}"
            )
            return False
        
        # Try to send the email
        mail.send(msg)
        logger.info(f"Email sent successfully to {msg.recipients}")
        return True
        
    except OSError as e:
        # Network/SMTP connection error
        logger.error(f"Email connection failed: {str(e)}. Make sure SMTP server is configured.")
        logger.error(f"Current config: MAIL_SERVER={current_app.config.get('MAIL_SERVER')}, "
                    f"MAIL_PORT={current_app.config.get('MAIL_PORT')}")
        return False
    except Exception as e:
        # Other errors
        logger.error(f"Failed to send email: {str(e)}")
        return False

# Email templates
ALERT_EMAIL_TEMPLATE = """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f5f5f5; }
        .container { max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
        .content { padding: 20px 0; }
        .alert-warning { background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 15px 0; }
        .alert-danger { background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 15px 0; }
        .footer { border-top: 1px solid #e0e0e0; padding-top: 15px; font-size: 12px; color: #999; }
        .button { display: inline-block; background-color: #3498db; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>💰 Budget Alert - {{ user_name }}</h2>
        </div>
        <div class="content">
            <p>Hi {{ user_name }},</p>
            
            {% if alert_type == 'budget_warning' %}
            <div class="alert-warning">
                <strong>⚠️ Budget Warning!</strong><br>
                You have spent <strong>${{ spent_amount }}</strong> of your <strong>${{ budget_amount }}</strong> monthly budget (<strong>{{ percentage }}%</strong>).
                <br><br>
                Please review your spending to avoid exceeding your budget.
            </div>
            {% elif alert_type == 'budget_exceeded' %}
            <div class="alert-danger">
                <strong>🚨 Budget Exceeded!</strong><br>
                You have exceeded your budget by <strong>${{ excess_amount }}</strong>. 
                <br>Budget: <strong>${{ budget_amount }}</strong> | Spent: <strong>${{ spent_amount }}</strong> (<strong>{{ percentage }}%</strong>)
                <br><br>
                Consider adjusting your spending or budget for next month.
            </div>
            {% endif %}
            
            <p><strong>Alert Date:</strong> {{ created_date }}</p>
            
            <a href="{{ app_url }}/dashboard" class="button">View Dashboard</a>
        </div>
        <div class="footer">
            <p>This is an automated alert from your Expense Tracker application.</p>
            <p>If you didn't set up budget alerts, you can manage them in your account settings.</p>
        </div>
    </div>
</body>
</html>
"""


def send_alert_email(user_id: int, alert_id: int) -> bool:
    """
    Send budget alert email to user.
    
    Args:
        user_id: ID of the user to send alert to
        alert_id: ID of the alert to send
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        user = User.query.get(user_id)
        alert = Alert.query.get(alert_id)
        
        if not user or not user.email or not alert:
            return False
        
        # Parse alert message for details
        spent_amount: float = 0.0
        budget_amount: float = 0.0
        percentage: float = 0.0
        
        # Extract values from alert message (format: "Spent: $X of $Y")
        if 'Spent:' in alert.message:
            parts = alert.message.split('of')
            if len(parts) == 2:
                spent_str = parts[0].replace('Spent: $', '').strip()
                budget_str = parts[1].replace('$', '').strip()
                try:
                    spent_amount = float(spent_str)
                    budget_amount = float(budget_str)
                    percentage = round((spent_amount / budget_amount) * 100, 1)
                except:
                    pass
        
        excess_amount: float = max(0, spent_amount - budget_amount)
        app_url: str = current_app.config.get('APP_URL', 'http://localhost:5000')
        
        # Render email template
        html_body: str = render_template_string(
            ALERT_EMAIL_TEMPLATE,
            user_name=user.username,
            alert_type=alert.alert_type,
            spent_amount=f"{spent_amount:.2f}",
            budget_amount=f"{budget_amount:.2f}",
            excess_amount=f"{excess_amount:.2f}",
            percentage=percentage,
            created_date=alert.created_at.strftime("%B %d, %Y at %I:%M %p"),
            app_url=app_url
        )
        
        # Create message
        msg: Message = Message(
            subject=f"💰 Expense Tracker Alert: {alert.title}",
            recipients=[user.email],
            html=html_body
        )
        
        # Send email with fallback
        success: bool = send_email_with_fallback(msg)
        
        # Mark alert as sent only if email was sent
        if success:
            alert.is_sent = True
            db.session.commit()
        
        return success
        
    except Exception as e:
        logger.error(f"Error processing alert email: {str(e)}")
        return False


def send_welcome_email(user_email: str, username: str) -> bool:
    """
    Send welcome email to new user.
    
    Args:
        user_email: Email address of new user
        username: Username of new user
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        welcome_template = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .container { max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; }
                .header { color: #3498db; }
                .features { margin: 20px 0; }
                .feature { margin: 10px 0; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Welcome to Expense Tracker!</h2>
                </div>
                <p>Hi {{ username }},</p>
                <p>Thank you for creating an account with Expense Tracker. You're all set to start managing your finances!</p>
                
                <div class="features">
                    <h3>Features you can use:</h3>
                    <div class="feature">✅ <strong>Track Expenses</strong> - Record all your daily expenses</div>
                    <div class="feature">✅ <strong>Budget Alerts</strong> - Get notified when approaching budget limits</div>
                    <div class="feature">✅ <strong>Analytics</strong> - View detailed spending trends and breakdowns</div>
                    <div class="feature">✅ <strong>Receipt Upload</strong> - Store receipts for your expenses</div>
                </div>
                
                <p>Get started by logging into your dashboard and adding your first expense!</p>
                
                <p>Best regards,<br>The Expense Tracker Team</p>
            </div>
        </body>
        </html>
        """
        
        msg: Message = Message(
            subject="Welcome to Expense Tracker!",
            recipients=[user_email],
            html=welcome_template.replace("{{ username }}", username)
        )
        
        return send_email_with_fallback(msg)
        
    except Exception as e:
        logger.error(f"Error processing welcome email: {str(e)}")
        return False


def send_monthly_summary_email(user_id: int) -> bool:
    """
    Send monthly spending summary email to user.
    
    Args:
        user_id: ID of the user to send summary to
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        user = User.query.get(user_id)
        
        if not user or not user.email:
            return False
        
        from utils import calculate_month_total, get_monthly_budget, calculate_category_spending
        from datetime import datetime
        
        month_total: float = calculate_month_total(user_id)
        budget: float = get_monthly_budget(user_id)
        expenses = Expense.query.filter_by(user_id=user_id).all()
        category_spending: dict = calculate_category_spending(expenses)
        
        # Find top category
        top_category: str = max(category_spending.items(), key=lambda x: x[1])[0] if category_spending else "N/A"
        top_amount: float = float(max(category_spending.values())) if category_spending else 0
        
        current_month: str = datetime.now().strftime("%B %Y")
        
        summary_template = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f5f5f5; }
                .container { max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; }
                .stat { display: inline-block; width: 45%; margin: 10px 2.5%; background-color: #f0f0f0; padding: 15px; border-radius: 4px; text-align: center; }
                .stat-value { font-size: 24px; font-weight: bold; color: #3498db; }
                .stat-label { font-size: 12px; color: #666; margin-top: 5px; }
            </style>
        </head>
        <body>
            <div class="container">
                <h2>Your {{ month }} Spending Summary</h2>
                <p>Hi {{ username }},</p>
                <p>Here's a summary of your spending for {{ month }}:</p>
                
                <div class="stat">
                    <div class="stat-value">${{ total_spent }}</div>
                    <div class="stat-label">Total Spent</div>
                </div>
                <div class="stat">
                    <div class="stat-value">${{ budget }}</div>
                    <div class="stat-label">Budget</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ percentage }}%</div>
                    <div class="stat-label">Budget Used</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{{ top_category }}</div>
                    <div class="stat-label">Top Category</div>
                </div>
                
                <p style="margin-top: 20px;">Keep tracking your expenses to better manage your finances!</p>
            </div>
        </body>
        </html>
        """
        
        percentage: float = round((month_total / budget * 100), 1) if budget > 0 else 0
        
        msg: Message = Message(
            subject=f"Your {current_month} Spending Summary",
            recipients=[user.email],
            html=summary_template.replace("{{ month }}", current_month)
                                  .replace("{{ username }}", user.username)
                                  .replace("{{ total_spent }}", f"{month_total:.2f}")
                                  .replace("{{ budget }}", f"{budget:.2f}")
                                  .replace("{{ percentage }}", str(percentage))
                                  .replace("{{ top_category }}", top_category)
        )
        
        return send_email_with_fallback(msg)
        
    except Exception as e:
        logger.error(f"Error processing monthly summary email: {str(e)}")
        return False


def send_password_reset_email(user_email: str, reset_url: str) -> bool:
    """
    Send password reset email.
    
    Args:
        user_email: Email address of user requesting reset
        reset_url: URL link for password reset (usually expires in 1 hour)
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        reset_template = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f5f5f5; }
                .container { max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .header { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                .content { padding: 20px 0; }
                .button { display: inline-block; background-color: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin: 15px 0; }
                .footer { border-top: 1px solid #e0e0e0; padding-top: 15px; font-size: 12px; color: #999; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>🔐 Password Reset Request</h2>
                </div>
                <div class="content">
                    <p>Hi,</p>
                    <p>You requested a password reset for your Expense Tracker account.</p>
                    <p>Click the button below to reset your password:</p>
                    
                    <a href="{{ reset_url }}" class="button">Reset Password</a>
                    
                    <p><strong>Important:</strong> This link will expire in 1 hour for security reasons.</p>
                    <p>If you didn't request this reset, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>If the button doesn't work, copy and paste this URL into your browser:<br>
                    {{ reset_url }}</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg: Message = Message(
            subject="Password Reset Request - Expense Tracker",
            recipients=[user_email],
            html=reset_template.replace("{{ reset_url }}", reset_url)
        )
        
        return send_email_with_fallback(msg)
        
    except Exception as e:
        logger.error(f"Error processing password reset email: {str(e)}")
        return False


def send_username_recovery_email(user_email: str, username: str) -> bool:
    """
    Send username recovery email.
    
    Args:
        user_email: Email address of user requesting username recovery
        username: Username to send in email
    
    Returns:
        True if email sent successfully, False otherwise
    """
    try:
        recovery_template = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; background-color: #f5f5f5; }
                .container { max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
                .header { border-bottom: 2px solid #3498db; padding-bottom: 10px; }
                .content { padding: 20px 0; }
                .username { font-size: 18px; font-weight: bold; color: #3498db; background-color: #f0f8ff; padding: 10px; border-radius: 4px; text-align: center; margin: 15px 0; }
                .footer { border-top: 1px solid #e0e0e0; padding-top: 15px; font-size: 12px; color: #999; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>👤 Username Recovery</h2>
                </div>
                <div class="content">
                    <p>Hi,</p>
                    <p>You requested your username for the Expense Tracker account associated with this email.</p>
                    <p>Your username is:</p>
                    
                    <div class="username">{{ username }}</div>
                    
                    <p>If you didn't request this, please ignore this email.</p>
                </div>
                <div class="footer">
                    <p>Keep this information secure and don't share it with others.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        msg: Message = Message(
            subject="Username Recovery - Expense Tracker",
            recipients=[user_email],
            html=recovery_template.replace("{{ username }}", username)
        )
        
        return send_email_with_fallback(msg)
        
    except Exception as e:
        logger.error(f"Error processing username recovery email: {str(e)}")
        return False
