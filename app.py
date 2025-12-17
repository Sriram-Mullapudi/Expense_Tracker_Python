from flask import Flask, render_template, request, redirect, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import io, csv
import os

app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'expenses.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=True)
    date = db.Column(db.Date, default=lambda: datetime.utcnow().date())

    def __repr__(self):
        return f'<Expense {self.title}>'

with app.app_context():
    db.create_all()

@app.route('/')
def index():
    # Filtering via query params
    q = Expense.query
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except ValueError:
            pass
    if category:
        q = q.filter(Expense.category == category)

    expenses = q.order_by(Expense.date.desc()).all()
    total = sum(e.amount for e in expenses)
    return render_template('index.html', expenses=expenses, total=total, date_from=date_from or '', date_to=date_to or '', category=category or '')

@app.route('/add', methods=['GET','POST'])
def add():
    if request.method == 'POST':
        title = request.form['title']
        amount = float(request.form['amount'])
        category = request.form.get('category')
        date_str = request.form.get('date')
        if date_str:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
        else:
            date = datetime.utcnow().date()
        exp = Expense(title=title, amount=amount, category=category, date=date)
        db.session.add(exp)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('add.html')


@app.route('/edit/<int:id>', methods=['GET', 'POST'])
def edit(id):
    exp = Expense.query.get_or_404(id)
    if request.method == 'POST':
        exp.title = request.form['title']
        exp.amount = float(request.form['amount'])
        exp.category = request.form.get('category')
        date_str = request.form.get('date')
        if date_str:
            exp.date = datetime.strptime(date_str, '%Y-%m-%d').date()
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('edit.html', expense=exp)

@app.route('/delete/<int:id>', methods=['POST'])
def delete(id):
    exp = Expense.query.get_or_404(id)
    db.session.delete(exp)
    db.session.commit()
    return redirect(url_for('index'))


def _filtered_query_from_args():
    q = Expense.query
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    category = request.args.get('category')
    if date_from:
        try:
            df = datetime.strptime(date_from, '%Y-%m-%d').date()
            q = q.filter(Expense.date >= df)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.strptime(date_to, '%Y-%m-%d').date()
            q = q.filter(Expense.date <= dt)
        except ValueError:
            pass
    if category:
        q = q.filter(Expense.category == category)
    return q


@app.route('/export')
def export_csv():
    q = _filtered_query_from_args().order_by(Expense.date.desc()).all()
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['id', 'date', 'title', 'category', 'amount'])
    for e in q:
        cw.writerow([e.id, e.date.isoformat(), e.title, e.category or '', '%.2f' % e.amount])
    output = si.getvalue()
    return Response(output, mimetype='text/csv', headers={
        'Content-Disposition': 'attachment; filename=expenses.csv'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='127.0.0.1', port=port)
