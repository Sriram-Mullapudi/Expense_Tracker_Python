import pytest

def test_login_page(client):
    resp = client.get('/login')
    assert resp.status_code == 200

def test_register_page(client):
    resp = client.get('/register')
    assert resp.status_code == 200
