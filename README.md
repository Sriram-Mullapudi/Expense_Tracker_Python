# Expense Tracker (Flask)

A lightweight, self-hosted expense tracker built with Flask and SQLite.

This repository contains a small Flask application for tracking personal expenses. It includes user authentication, expense CRUD, filtering, CSV export, simple settings (monthly budget), and a responsive dashboard with charts.

---

## Features

- User registration and login (Flask-Login)
- Add, edit, delete expenses (title, date, category, amount, description)
- Filter expenses by date range, month, and category
- Export filtered expenses to CSV
- Per-user settings (monthly budget) with budget warning
- Dashboard with quick stats and spending-by-category chart
- Lightweight SQLite storage (created automatically)

---

## Getting Started (local development)

Prerequisites:

- Python 3.8+ (3.10/3.11 recommended)
- A terminal (PowerShell on Windows, bash on macOS/Linux)

1. Clone the repo (optional):

```bash
git clone <repo-url> expense-tracker
cd expense-tracker
```

2. Create and activate a virtual environment

Windows (PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

macOS / Linux:

```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies

```bash
pip install -r requirements.txt
```

4. Start the app (development)

```bash
python app.py
```

5. Open the app in your browser:

```
http://127.0.0.1:5000
```

Notes:

- The first run will create a SQLite database file and necessary tables automatically using SQLAlchemy's `db.create_all()`.
- If you change the database models and need a fresh schema, stop the app and delete any `.db` files, then restart to recreate the database.

---

## Project structure

- `app.py` — main Flask application (routes, models, helper functions)
- `requirements.txt` — Python package requirements
- `templates/` — Jinja2 templates used by Flask
- `static/` — CSS and static assets
- `expenses.db` or similar — SQLite database file (auto-generated at runtime)

---

## UI and Styling

The UI uses Bootstrap 5 and a custom `static/style.css` for a professional dashboard look. If you want to tweak colors or spacing, edit that file only — no changes to `app.py` are required for cosmetic updates.

---

## Environment Configuration

For production deployments, copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Edit `.env` with your settings:

```env
SECRET_KEY=your-secure-random-key
FLASK_ENV=production
FLASK_DEBUG=False
SQLALCHEMY_DATABASE_URI=sqlite:///expenses.db
```

The app loads from the `.env` file if present, otherwise uses hardcoded defaults.

---

## Testing

Run the test suite with pytest:

```bash
pytest -q
```

Tests verify basic functionality (login page, registration page, database models). Run tests before committing changes.

---

## Deployment

For local development, follow the [Getting Started](#getting-started-local-development) section.

For production deployment (Heroku, AWS, DigitalOcean, Docker, etc.), see [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Troubleshooting

- **UndefinedError in templates**: Ensure you logged in before accessing the dashboard. Many template variables are per-user.
- **OperationalError: no such column**: Delete the `.db` file and restart the app to recreate the schema.
- **Port already in use**: Kill the process using port 5000 or change the port in `app.py`.
- **ImportError for flask_migrate**: Run `pip install -r requirements.txt` to install all dependencies, or delete `migrations/` to run without migrations.

---

## Development notes (for maintainers)

- **Framework**: Flask 3.1.2, Flask-SQLAlchemy, Flask-Login, Flask-Migrate (optional)
- **Frontend**: Bootstrap 5, custom CSS in `static/style.css`, Jinja2 templates
- **Database**: SQLite with SQLAlchemy ORM (auto-creates schema on startup)
- **Charts**: Chart.js for category spending visualization
- **Testing**: pytest with in-memory SQLite fixtures
- **CI/CD**: GitHub Actions workflow for automated testing

**File structure**:
- `app.py` — Core Flask app with routes, models, and logic
- `templates/` — Jinja2 templates (6 files: base, index, add, edit, login, register, settings)
- `static/style.css` — Professional CSS with light/dark mode
- `tests/` — pytest smoke tests
- `migrations/` — Alembic schema migrations (Flask-Migrate)
- `Dockerfile`, `docker-compose.yml` — Container orchestratio
- `Procfile`, `start.sh`, `start.ps1` — Deployment and startup scripts
- `Makefile` — Common development tasks

---

## License

MIT License. See [LICENSE](LICENSE) file for details.

