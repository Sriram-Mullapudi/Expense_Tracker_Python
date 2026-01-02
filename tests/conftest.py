import os
import sys
import pytest

# Ensure project root is on sys.path so tests can import `app`
proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from app import app as flask_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    # Use a temporary instance folder / database
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False

    # Use an in-memory sqlite to avoid file DB during tests
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'

    with flask_app.test_client() as client:
        with flask_app.app_context():
            from app import db
            db.create_all()
        yield client
