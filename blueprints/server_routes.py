"""Server pages: dashboard, detail, export, and removal."""

from flask import Blueprint, Response, abort, current_app, flash, redirect, render_template, request, url_for

import db
from auth import _require_csrf, login_required
from blueprints import database_path
from present import present, samples_to_csv, server_row
from schemas import parse_server_form
from services.metrics import record_server_metrics

servers_bp = Blueprint("servers", __name__)


@servers_bp.get("/")
@login_required
def dashboard():
    servers = [server_row(row) for row in db.list_servers(database_path())]
    return _dashboard(servers, form_error=None, form_name="", form_ip="")


@servers_bp.post("/servers")
@login_required
def add_server():
    _require_csrf()
    parsed = parse_server_form(request.form)
    if not parsed["is_valid"]:
        current_app.logger.info("Rejected server form")
        servers = [server_row(row) for row in db.list_servers(database_path())]
        return _dashboard(
            servers,
            form_error=parsed["error"],
            form_name=parsed["name"],
            form_ip=parsed["ip"],
        ), 400
    db.add_server(database_path(), parsed["name"], parsed["ip"])
    flash("Server added.", "success")
    return redirect(url_for("servers.dashboard"))


@servers_bp.get("/servers/<int:server_id>")
@login_required
def server_detail(server_id: int):
    server = db.get_server(database_path(), server_id)
    if server is None:
        abort(404)
    recorded = record_server_metrics(database_path(), server)
    return render_template(
        "server.html",
        server=server,
        metrics=present(server, recorded["error"], recorded["samples"]),
    )


@servers_bp.get("/servers/<int:server_id>/export")
@login_required
def export_csv(server_id: int):
    server = db.get_server(database_path(), server_id)
    if server is None:
        abort(404)
    response = Response(
        samples_to_csv(db.list_samples(database_path(), server_id)),
        mimetype="text/csv",
    )
    response.headers["Content-Disposition"] = (
        f"attachment; filename=server-{server_id}-metrics.csv"
    )
    return response


@servers_bp.post("/servers/<int:server_id>/delete")
@login_required
def delete_server(server_id: int):
    _require_csrf()
    if not db.delete_server(database_path(), server_id):
        abort(404)
    flash("Server removed.", "success")
    return redirect(url_for("servers.dashboard"))


def _dashboard(servers: list[dict], form_error, form_name: str, form_ip: str):
    return render_template(
        "dashboard.html",
        servers=servers,
        form_error=form_error,
        form_name=form_name,
        form_ip=form_ip,
    )
