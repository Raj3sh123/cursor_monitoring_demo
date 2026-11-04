"""Local demo for Linux server CPU, memory, network, and listening ports."""

import csv
import io
import json
import os
import secrets
from functools import wraps

from flask import (
    Flask,
    Response,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

import db
from collector import collect_metrics, is_alert, is_valid_ip

NAME_MAX_LENGTH = 64
REFRESH_MS = 5000
DEV_SECRET_KEY = "dev-only-local-key"


def create_app(test_config=None):
    _load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY") or DEV_SECRET_KEY
    app.config["DATABASE"] = os.environ.get("DATABASE") or os.path.join(
        os.path.dirname(__file__), "monitor.db"
    )
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if test_config:
        app.config.update(test_config)

    db.init_db(app.config["DATABASE"])

    def database():
        return app.config["DATABASE"]

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if session.get("user_id") is None:
                if request.path.endswith("/metrics"):
                    return jsonify({"ok": False, "error": "Authentication required"}), 401
                return redirect(url_for("login"))
            return view(*args, **kwargs)

        return wrapped

    @app.before_request
    def ensure_csrf():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.after_request
    def secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": session.get("csrf_token", ""),
            "current_user": session.get("username"),
            "status_class": _status_class,
        }

    @app.get("/login")
    def login():
        if session.get("user_id") is not None:
            return redirect(url_for("dashboard"))
        return render_template("login.html", error=None)

    @app.post("/login")
    def login_post():
        _require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db.get_user(database(), username)
        password_ok = False
        if user is not None:
            password_ok = check_password_hash(user["password_hash"], password)
        else:
            check_password_hash(_dummy_hash(), password)
        if not password_ok:
            return render_template("login.html", error="Invalid username or password."), 401
        session.clear()
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["csrf_token"] = secrets.token_urlsafe(32)
        return redirect(url_for("dashboard"))

    @app.post("/logout")
    def logout():
        _require_csrf()
        session.clear()
        return redirect(url_for("login"))

    @app.get("/")
    @login_required
    def dashboard():
        servers = [_server_row(row) for row in db.list_servers(database())]
        return render_template(
            "dashboard.html",
            servers=servers,
            form_error=None,
            form_name="",
            form_ip="",
        )

    @app.post("/servers")
    @login_required
    def add_server():
        _require_csrf()
        name = request.form.get("name", "").strip()
        ip = request.form.get("ip", "").strip()
        error = _validate_server(name, ip)
        if error:
            servers = [_server_row(row) for row in db.list_servers(database())]
            return render_template(
                "dashboard.html",
                servers=servers,
                form_error=error,
                form_name=name,
                form_ip=ip,
            ), 400
        db.add_server(database(), name, ip)
        flash("Server added.", "success")
        return redirect(url_for("dashboard"))

    @app.get("/servers/<int:server_id>")
    @login_required
    def server_detail(server_id):
        server = db.get_server(database(), server_id)
        if server is None:
            abort(404)
        metrics = _collect_and_present(server)
        return render_template("server.html", server=server, metrics=metrics)

    @app.get("/servers/<int:server_id>/metrics")
    @login_required
    def server_metrics(server_id):
        server = db.get_server(database(), server_id)
        if server is None:
            return jsonify({"ok": False, "error": "Server not found."}), 404
        return jsonify(_collect_and_present(server))

    @app.get("/servers/<int:server_id>/export")
    @login_required
    def export_csv(server_id):
        server = db.get_server(database(), server_id)
        if server is None:
            abort(404)
        samples = db.list_samples(database(), server_id)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(
            [
                "collected_at",
                "cpu_percent",
                "mem_used_bytes",
                "mem_total_bytes",
                "mem_percent",
                "network",
                "ports",
            ]
        )
        for sample in samples:
            mem_percent = _memory_percent(sample["mem_used"], sample["mem_total"])
            writer.writerow(
                [
                    sample["collected_at"],
                    sample["cpu_percent"],
                    sample["mem_used"],
                    sample["mem_total"],
                    mem_percent,
                    sample["network_json"],
                    sample["ports_json"],
                ]
            )
        response = Response(buffer.getvalue(), mimetype="text/csv")
        response.headers["Content-Disposition"] = (
            f"attachment; filename=server-{server_id}-metrics.csv"
        )
        return response

    @app.post("/servers/<int:server_id>/delete")
    @login_required
    def delete_server(server_id):
        _require_csrf()
        if not db.delete_server(database(), server_id):
            abort(404)
        flash("Server removed.", "success")
        return redirect(url_for("dashboard"))

    def _collect_and_present(server):
        result = collect_metrics(server["ip"])
        if result["ok"]:
            db.add_sample(
                database(),
                server["id"],
                result["cpu_percent"],
                result["mem_used"],
                result["mem_total"],
                json.dumps(result["network"]),
                json.dumps(result["ports"]),
            )
        samples = db.list_samples(database(), server["id"])
        error = None if result["ok"] else result["error"]
        return _present(server, error, samples)

    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("error.html", message="Invalid request."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", message="Page not found."), 404

    return app


def _require_csrf():
    token = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not token or not expected or not secrets.compare_digest(token, expected):
        abort(400)


def _validate_server(name, ip):
    if not name or len(name) > NAME_MAX_LENGTH:
        return f"Name must be 1 to {NAME_MAX_LENGTH} characters."
    if not is_valid_ip(ip):
        return "Enter a valid IP address."
    return None


def _dummy_hash():
    if not hasattr(_dummy_hash, "value"):
        from werkzeug.security import generate_password_hash

        _dummy_hash.value = generate_password_hash("invalid-user")
    return _dummy_hash.value


def _server_row(row):
    mem_percent = _memory_percent(row.get("mem_used"), row.get("mem_total"))
    cpu = row.get("cpu_percent")
    if row.get("collected_at") is None:
        status = "No data"
    elif is_alert(cpu, mem_percent):
        status = "Alert"
    else:
        status = "OK"
    return {
        "id": row["id"],
        "name": row["name"],
        "ip": row["ip"],
        "cpu_display": _format_percent(cpu),
        "mem_display": _format_percent(mem_percent),
        "status": status,
    }


def _present(server, error, samples):
    latest = samples[-1] if samples else None
    previous = samples[-2] if len(samples) > 1 else None
    cpu = latest["cpu_percent"] if latest else None
    mem_percent = _memory_percent(
        latest["mem_used"] if latest else None,
        latest["mem_total"] if latest else None,
    )
    network = _network_rows(latest, previous)
    ports = json.loads(latest["ports_json"]) if latest and latest["ports_json"] else []
    alert = bool(latest) and is_alert(cpu, mem_percent)
    if error:
        status = "Error"
    elif latest is None:
        status = "No data"
    elif alert:
        status = "Alert"
    else:
        status = "OK"
    return {
        "ok": error is None and latest is not None,
        "error": error,
        "server": {"id": server["id"], "name": server["name"], "ip": server["ip"]},
        "collected_at": _display_time(latest["collected_at"]) if latest else None,
        "cpu_percent": cpu,
        "cpu_display": _format_percent(cpu),
        "memory": {
            "percent": mem_percent,
            "percent_display": _format_percent(mem_percent),
            "used_display": _format_bytes(latest["mem_used"]) if latest else "—",
            "total_display": _format_bytes(latest["mem_total"]) if latest else "—",
            "available_display": _format_bytes(_available_bytes(latest)) if latest else "—",
        },
        "network": network,
        "ports": ports,
        "alert": alert,
        "status": status,
        "history": _history(samples),
        "refresh_ms": REFRESH_MS,
    }


def _available_bytes(sample):
    if not sample or sample["mem_total"] is None or sample["mem_used"] is None:
        return None
    return max(0, sample["mem_total"] - sample["mem_used"])


def _network_rows(latest, previous):
    if not latest or not latest["network_json"]:
        return []
    current = json.loads(latest["network_json"])
    prior = json.loads(previous["network_json"]) if previous and previous["network_json"] else []
    prior_by_iface = {row["iface"]: row for row in prior}
    seconds = _seconds_between(
        previous["collected_at"] if previous else None,
        latest["collected_at"],
    )
    rows = []
    for row in current:
        rx_rate = None
        tx_rate = None
        old = prior_by_iface.get(row["iface"])
        if old and seconds > 0:
            rx_rate = max(0, (row["rx_bytes"] - old["rx_bytes"]) / seconds)
            tx_rate = max(0, (row["tx_bytes"] - old["tx_bytes"]) / seconds)
        rows.append(
            {
                "iface": row["iface"],
                "rx_display": _format_bytes(row["rx_bytes"]),
                "tx_display": _format_bytes(row["tx_bytes"]),
                "rx_rate_display": _format_rate(rx_rate),
                "tx_rate_display": _format_rate(tx_rate),
            }
        )
    return rows


def _history(samples):
    labels = []
    cpu = []
    memory = []
    for sample in samples:
        stamp = sample["collected_at"]
        labels.append(stamp[11:19] if len(stamp) >= 19 else stamp)
        cpu.append(sample["cpu_percent"])
        memory.append(_memory_percent(sample["mem_used"], sample["mem_total"]))
    return {"labels": labels, "cpu": cpu, "memory": memory}


def _seconds_between(start, end):
    if not start or not end:
        return 0
    from datetime import datetime

    try:
        delta = datetime.fromisoformat(end) - datetime.fromisoformat(start)
    except ValueError:
        return 0
    return delta.total_seconds()


def _memory_percent(used, total):
    if used is None or not total:
        return None
    return round(used / total * 100, 1)


def _status_class(status):
    if status == "Alert":
        return "text-bg-danger"
    if status == "OK":
        return "text-bg-success"
    if status == "Error":
        return "text-bg-warning"
    return "text-bg-secondary"


def _format_percent(value):
    if value is None:
        return "—"
    return f"{value:.1f}%"


def _format_bytes(value):
    if value is None:
        return "—"
    number = float(value)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if number < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(number)} {unit}"
            return f"{number:.1f} {unit}"
        number /= 1024
    return f"{number:.1f} TB"


def _format_rate(value):
    if value is None:
        return "—"
    return f"{_format_bytes(value)}/s"


def _display_time(value):
    if not value:
        return None
    return value.replace("T", " ")[:19] + " UTC"


def _load_dotenv(path):
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ.setdefault(key, value)


app = create_app()


if __name__ == "__main__":
    # Demo only: listen on localhost so the app is not exposed on the network.
    app.run(host="127.0.0.1", port=5000, debug=False)
