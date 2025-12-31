from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, date
import calendar
import csv
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    expenses = db.relationship('Expense', backref='user', lazy=True)
    settings = db.relationship('Setting', backref='user', lazy=True)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(500))

class Setting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    key = db.Column(db.String(50), nullable=False)
    value = db.Column(db.String(500))

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def get_setting(key):
    setting = Setting.query.filter_by(user_id=current_user.id, key=key).first()
    return setting.value if setting else None

def set_setting(key, value):
    setting = Setting.query.filter_by(user_id=current_user.id, key=key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(user_id=current_user.id, key=key, value=value)
        db.session.add(setting)
    db.session.commit()

def parse_month(month_str):
    try:
        year, month = map(int, month_str.split('-'))
        first = date(year, month, 1)
        last_day = calendar.monthrange(year, month)[1]
        last = date(year, month, last_day)
        return first, last
    except:
        return None, None

@app.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete(id):
    e = Expense.query.get_or_404(id)

    if e.user_id != current_user.id:
        flash('Unauthorized', 'warning')
        return redirect(url_for('index'))

    db.session.delete(e)
    db.session.commit()
    flash('Expense deleted', 'info')
    return redirect(url_for('index'))


@app.route('/export')
@login_required
def export_csv():
    # same filters as index
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    month = request.args.get('month')

    q = Expense.query.filter_by(user_id=current_user.id)

    if month:
        first, last = parse_month(month)
        if first and last:
            q = q.filter(Expense.date >= first, Expense.date <= last)

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except:
            pass

    if category and category.lower() != 'all':
        q = q.filter_by(category=category)

    items = q.order_by(Expense.date.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['id', 'date', 'title', 'category', 'amount', 'description'])

    for it in items:
        writer.writerow([
            it.id,
            it.date.isoformat(),
            it.title,
            it.category,
            f"{it.amount:.2f}",
            it.description or ''
        ])

    resp = Response(output.getvalue(), mimetype='text/csv')
    resp.headers["Content-Disposition"] = "attachment; filename=expenses.csv"
    return resp


@app.route('/settings', methods=['GET','POST'])
@login_required
def settings():
    if request.method == 'POST':
        monthly_budget = request.form.get('monthly_budget') or ''
        set_setting('monthly_budget', monthly_budget)
        flash('Settings updated', 'success')
        return redirect(url_for('index'))

    current_budget = get_setting('monthly_budget') or ''

    today = datetime.utcnow().date()
    month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= date(today.year, today.month, 1),
        Expense.date <= date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    ).all()

    month_total = sum(e.amount for e in month_expenses)

    remaining_budget = 0
    budget_value = 0
    if current_budget:
        try:
            budget_value = float(current_budget)
            remaining_budget = budget_value - month_total
        except:
            budget_value = 0
            remaining_budget = 0

    return render_template(
        'settings.html',
        monthly_budget=current_budget,
        budget_value=budget_value,
        month_total=month_total,
        remaining_budget=remaining_budget
    )
@app.route('/')
@login_required
def index():
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category', 'all')
    month = request.args.get('month')

    q = Expense.query.filter_by(user_id=current_user.id)

    if month:
        first, last = parse_month(month)
        if first and last:
            q = q.filter(Expense.date >= first, Expense.date <= last)

    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except:
            pass

    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except:
            pass

    if category and category.lower() != 'all':
        q = q.filter_by(category=category)

    expenses = q.order_by(Expense.date.desc()).all()
    all_categories = [c[0] for c in db.session.query(Expense.category).filter_by(user_id=current_user.id).distinct().all()]
    
    filters = {
        'date_from': date_from or '',
        'date_to': date_to or '',
        'category': category,
        'month': month or ''
    }

    # Calculate statistics
    total_spent = sum(e.amount for e in expenses)
    
    today = date.today()
    today_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date == today
    ).all()
    today_total = sum(e.amount for e in today_expenses)
    
    month_expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.date >= date(today.year, today.month, 1),
        Expense.date <= date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
    ).all()
    month_total = sum(e.amount for e in month_expenses)
    
    budget_str = get_setting('monthly_budget') or ''
    budget = 0
    budget_warning = False
    if budget_str:
        try:
            budget = float(budget_str)
            if month_total > budget:
                budget_warning = True
        except:
            pass

    # Category spending breakdown
    category_spending = {}
    for expense in expenses:
        if expense.category not in category_spending:
            category_spending[expense.category] = 0
        category_spending[expense.category] += expense.amount
    
    category_labels = list(category_spending.keys())
    category_values = list(category_spending.values())

    return render_template('index.html', 
                         expenses=expenses, 
                         all_categories=all_categories, 
                         filters=filters,
                         total_spent=total_spent,
                         today_total=today_total,
                         month_total=month_total,
                         budget=budget,
                         budget_warning=budget_warning,
                         category_labels=category_labels,
                         category_values=category_values)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid credentials', 'warning')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'warning')
        else:
            user = User(username=username, password=generate_password_hash(password))
            db.session.add(user)
            db.session.commit()
            flash('Account created successfully. Please login.', 'success')
            return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add():
    if request.method == 'POST':
        date_str = request.form.get('date')
        title = request.form.get('title')
        category = request.form.get('category')
        amount = request.form.get('amount')
        description = request.form.get('description')

        try:
            expense_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            amount_float = float(amount)

            expense = Expense(
                user_id=current_user.id,
                date=expense_date,
                title=title,
                category=category,
                amount=amount_float,
                description=description
            )
            db.session.add(expense)
            db.session.commit()
            flash('Expense added successfully', 'success')
            return redirect(url_for('index'))
        except:
            flash('Invalid input', 'danger')

    return render_template('add.html')

@app.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    expense = Expense.query.get_or_404(id)

    if expense.user_id != current_user.id:
        flash('Unauthorized', 'warning')
        return redirect(url_for('index'))

    if request.method == 'POST':
        date_str = request.form.get('date')
        title = request.form.get('title')
        category = request.form.get('category')
        amount = request.form.get('amount')
        description = request.form.get('description')

        try:
            expense.date = datetime.strptime(date_str, '%Y-%m-%d').date()
            expense.title = title
            expense.category = category
            expense.amount = float(amount)
            expense.description = description

            db.session.commit()
            flash('Expense updated successfully', 'success')
            return redirect(url_for('index'))
        except:
            flash('Invalid input', 'danger')

    return render_template('edit.html', expense=expense)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)