import json

import pytest

import db
from app import create_app
from db import HISTORY_LIMIT


@pytest.fixture
def app(tmp_path):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret",
            "DATABASE": str(tmp_path / "test.db"),
        }
    )
    return application


@pytest.fixture
def client(app):
    return app.test_client()


def _csrf(client):
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def _login(client, username="admin", password="admin123"):
    client.get("/login")
    return client.post(
        "/login",
        data={"username": username, "password": password, "csrf_token": _csrf(client)},
    )


def _sample_metrics(cpu=10.0, memory_percent=20.0):
    total = 1000
    used = int(total * memory_percent / 100)
    return {
        "ok": True,
        "error": None,
        "cpu_percent": cpu,
        "mem_used": used,
        "mem_total": total,
        "mem_available": total - used,
        "mem_percent": memory_percent,
        "network": [{"iface": "eth0", "rx_bytes": 100, "tx_bytes": 50}],
        "ports": [{"proto": "tcp", "address": "0.0.0.0", "port": 22}],
    }


def test_good_login(client):
    response = _login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    page = client.get("/")
    assert page.status_code == 200
    assert b"Dashboard" in page.data


def test_bad_password(client):
    response = _login(client, password="wrong-password")
    assert response.status_code == 401
    assert b"Invalid username or password." in response.data
    assert b"wrong-password" not in response.data
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_protected_route_redirects(client):
    response = client.get("/")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    detail = client.get("/servers/1")
    assert detail.status_code == 302
    assert detail.headers["Location"].endswith("/login")


def test_password_is_stored_as_hash(app):
    user = db.get_user(app.config["DATABASE"], "admin")
    assert user["password_hash"] != "admin123"
    assert user["password_hash"].startswith(("scrypt:", "pbkdf2:"))
    raw = open(app.config["DATABASE"], "rb").read()
    assert b"admin123" not in raw


def test_login_requires_csrf(client):
    response = client.post("/login", data={"username": "admin", "password": "admin123"})
    assert response.status_code == 400


def test_add_and_remove_server(client):
    _login(client)
    client.get("/")
    created = client.post(
        "/servers",
        data={"name": "web-1", "ip": "192.0.2.10", "csrf_token": _csrf(client)},
    )
    assert created.status_code == 302
    page = client.get("/")
    assert b"web-1" in page.data
    assert b"192.0.2.10" in page.data

    removed = client.post("/servers/1/delete", data={"csrf_token": _csrf(client)})
    assert removed.status_code == 302
    page = client.get("/")
    assert b"web-1" not in page.data
    assert b"No servers registered." in page.data


def test_invalid_ip_is_rejected(client):
    _login(client)
    client.get("/")
    response = client.post(
        "/servers",
        data={"name": "bad", "ip": "not-an-ip", "csrf_token": _csrf(client)},
    )
    assert response.status_code == 400
    assert b"valid IP" in response.data
    assert db.list_servers(client.application.config["DATABASE"]) == []


def test_metrics_require_login_and_are_scoped(client, monkeypatch):
    monkeypatch.setattr("collector.collect_metrics", lambda ip: _sample_metrics(91.0, 90.0))
    logged_out = client.get("/servers/1/metrics")
    assert logged_out.status_code == 401

    _login(client)
    client.get("/")
    client.post(
        "/servers",
        data={"name": "alpha", "ip": "192.0.2.11", "csrf_token": _csrf(client)},
    )
    client.post(
        "/servers",
        data={"name": "beta", "ip": "192.0.2.12", "csrf_token": _csrf(client)},
    )
    response = client.get("/servers/1/metrics")
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["server"] == {"id": 1, "name": "alpha", "ip": "192.0.2.11"}
    assert payload["alert"] is True
    assert "beta" not in json.dumps(payload)
    assert "admin123" not in json.dumps(payload)
    body = response.get_data(as_text=True)
    assert "SSH_PASSWORD" not in body
    assert "SECRET_KEY" not in body


def test_csv_contains_metrics_only(client, monkeypatch):
    monkeypatch.setattr("collector.collect_metrics", lambda ip: _sample_metrics())
    _login(client)
    client.get("/")
    client.post(
        "/servers",
        data={"name": "edge", "ip": "2001:db8::1", "csrf_token": _csrf(client)},
    )
    client.get("/servers/1")
    denied = client.get("/logout")
    assert denied.status_code == 405
    export = client.get("/servers/1/export")
    text = export.get_data(as_text=True)
    assert export.mimetype == "text/csv"
    assert "cpu_percent" in text
    assert "eth0" in text
    assert "admin123" not in text
    assert "SECRET" not in text
    assert "BEGIN OPENSSH" not in text


def test_history_keeps_last_60_samples(client, monkeypatch):
    monkeypatch.setattr("collector.collect_metrics", lambda ip: _sample_metrics())
    _login(client)
    client.get("/")
    client.post(
        "/servers",
        data={"name": "hist", "ip": "192.0.2.20", "csrf_token": _csrf(client)},
    )
    for _ in range(HISTORY_LIMIT + 5):
        client.get("/servers/1/metrics")
    samples = db.list_samples(client.application.config["DATABASE"], 1)
    assert len(samples) == HISTORY_LIMIT


def test_metrics_accept_bearer_token(client, app, monkeypatch):
    monkeypatch.setattr("collector.collect_metrics", lambda ip: _sample_metrics())
    _login(client)
    client.get("/")
    client.post(
        "/servers",
        data={"name": "jwt", "ip": "192.0.2.40", "csrf_token": _csrf(client)},
    )
    with client.session_transaction() as sess:
        token = sess["access_token"]
    anonymous = app.test_client()
    response = anonymous.get(
        "/servers/1/metrics",
        headers={"Authorization": f"Bearer {token}"},
    )
    payload = response.get_json()
    assert response.status_code == 200
    assert payload["server"]["name"] == "jwt"
    assert token not in response.get_data(as_text=True)
    spec = anonymous.get("/api/openapi.json")
    assert spec.status_code == 200
    document = spec.get_data(as_text=True)
    assert "/servers/{server_id}/metrics" in document
    assert "admin123" not in document
    assert "SECRET" not in document


def test_ssh_failure_is_shown(client, monkeypatch):
    monkeypatch.setattr(
        "collector.collect_metrics",
        lambda ip: {"ok": False, "error": "SSH authentication failed."},
    )
    _login(client)
    client.get("/")
    client.post(
        "/servers",
        data={"name": "down", "ip": "192.0.2.30", "csrf_token": _csrf(client)},
    )
    page = client.get("/servers/1")
    assert page.status_code == 200
    assert b"SSH authentication failed." in page.data
    assert b"Export CSV" in page.data
