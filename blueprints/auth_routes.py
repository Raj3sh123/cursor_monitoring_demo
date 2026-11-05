"""Sign-in and sign-out routes."""

import secrets

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for
from flask_jwt_extended import create_access_token

from auth import _require_csrf
from blueprints import database_path
from services.auth import authenticate

auth_bp = Blueprint("auth", __name__)


@auth_bp.get("/login")
def login():
    if session.get("user_id") is not None:
        return redirect(url_for("servers.dashboard"))
    return render_template("login.html", error=None)


@auth_bp.post("/login")
def login_post():
    _require_csrf()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    identity = authenticate(database_path(), username, password)
    if identity is None:
        current_app.logger.info("Rejected sign-in")
        return render_template("login.html", error="Invalid username or password."), 401
    session.clear()
    session["user_id"] = identity["id"]
    session["username"] = identity["username"]
    session["csrf_token"] = secrets.token_urlsafe(32)
    session["access_token"] = create_access_token(identity=str(identity["id"]))
    return redirect(url_for("servers.dashboard"))


@auth_bp.post("/logout")
def logout():
    _require_csrf()
    session.clear()
    return redirect(url_for("auth.login"))
