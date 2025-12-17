# Expense Tracker (Flask)

Lightweight expense tracker built with Flask and SQLite. This repository contains the application, templates, and static assets to run locally.

## Prerequisites

- Python 3.8 or newer
- Git (optional)

## Quickstart — Windows (PowerShell)

```powershell
python -m venv venv
venv\Scripts\Activate
pip install -r requirements.txt
python app.py
```

## Quickstart — macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

After starting the app, open http://127.0.0.1:5000 in your browser.

## Files and structure

- `app.py`: Flask application, routes, and SQLAlchemy model
- `templates/`: Jinja2 templates (`base.html`, `index.html`, `add.html`)
- `static/style.css`: small stylesheet
- `requirements.txt`: Python dependencies

## Database

The app uses SQLite. The database file `expenses.db` is created in the project root on first run.

To reset the data, stop the app and delete `expenses.db`, then restart.

## Basic usage

- Open the homepage and use **Add Expense** to create records (title, amount, category, date).
- Expenses appear in the table; use the **Delete** button to remove an entry.
- The table footer shows the current total.

## Common commands

Activate virtual environment (Windows PowerShell):

```powershell
venv\Scripts\Activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the app (development):

```bash
python app.py
```

## Notes & next steps

- For production use, run behind a WSGI server (Gunicorn/Waitress) and configure host/port appropriately.
- You can extend the app with edit/update features, filtering, CSV export, or user authentication.

If you'd like, I can run the app now to verify it starts, or add one of the features above.

## New features added

- Edit/update existing expenses via the **Edit** button on the list view.
- Filter expenses by date range and category using the filter inputs on the homepage.
- Export the current filtered list as CSV via the **Export CSV** button.

These features are available locally after pulling the latest changes.

