"""Service behavior that does not go through HTTP."""

import db
from present import samples_to_csv
from services.auth import authenticate
from services.metrics import record_server_metrics


def _sample(ip):
    assert ip == "192.0.2.15"
    return {
        "ok": True,
        "error": None,
        "cpu_percent": 10.0,
        "mem_used": 200,
        "mem_total": 1000,
        "network": [{"iface": "eth0", "rx_bytes": 100, "tx_bytes": 50}],
        "ports": [{"proto": "tcp", "address": "0.0.0.0", "port": 22}],
    }


def test_authenticate_returns_identity_without_hash(tmp_path):
    path = str(tmp_path / "auth.db")
    db.init_db(path)
    identity = authenticate(path, "admin", "admin123")
    assert identity == {"id": 1, "username": "admin"}
    assert "password_hash" not in identity
    assert "admin123" not in str(identity)


def test_authenticate_rejects_unknown_user_and_bad_password(tmp_path):
    path = str(tmp_path / "auth.db")
    db.init_db(path)
    assert authenticate(path, "admin", "wrong-password") is None
    assert authenticate(path, "missing", "wrong-password") is None


def test_record_server_metrics_stores_a_sample(tmp_path):
    path = str(tmp_path / "metrics.db")
    db.init_db(path)
    server_id = db.add_server(path, "edge", "192.0.2.15")
    server = db.get_server(path, server_id)
    recorded = record_server_metrics(path, server, collect_metrics=_sample)
    assert recorded["error"] is None
    assert len(recorded["samples"]) == 1
    assert recorded["samples"][0]["cpu_percent"] == 10.0
    text = samples_to_csv(recorded["samples"])
    assert "cpu_percent" in text
    assert "eth0" in text


def test_record_server_metrics_reports_ssh_failure(tmp_path):
    path = str(tmp_path / "metrics.db")
    db.init_db(path)
    server_id = db.add_server(path, "down", "192.0.2.30")
    server = db.get_server(path, server_id)
    recorded = record_server_metrics(
        path,
        server,
        collect_metrics=lambda ip: {"ok": False, "error": "SSH authentication failed."},
    )
    assert recorded["error"] == "SSH authentication failed."
    assert recorded["samples"] == []
