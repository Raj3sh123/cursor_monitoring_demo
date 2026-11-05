"""Session and JWT checks for protected routes."""

import secrets
from functools import wraps

from flask import abort, jsonify, redirect, request, session, url_for
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request


def is_authenticated() -> bool:
    if session.get("user_id") is not None:
        return True
    if not request.headers.get("Authorization"):
        return False
    try:
        verify_jwt_in_request(optional=True)
    except Exception:
        return False
    return get_jwt_identity() is not None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if is_authenticated():
            return view(*args, **kwargs)
        if request.path.endswith("/metrics"):
            body = jsonify({"ok": False, "error": "Authentication required"})
            body.status_code = 401
            return body
        return redirect(url_for("auth.login"))

    return wrapped


def _require_csrf() -> None:
    token = request.form.get("csrf_token", "")
    expected = session.get("csrf_token", "")
    if not token or not expected or not secrets.compare_digest(token, expected):
        abort(400)

