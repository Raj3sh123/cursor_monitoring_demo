"""Check a username and password. Callers never see the stored hash."""

from werkzeug.security import check_password_hash, generate_password_hash

import db


def authenticate(database: str, username: str, password: str) -> dict | None:
    user = db.get_user(database, username)
    if user is None:
        check_password_hash(_dummy_hash(), password)
        return None
    if not check_password_hash(user["password_hash"], password):
        return None
    return {"id": user["id"], "username": user["username"]}


def _dummy_hash() -> str:
    if not hasattr(_dummy_hash, "value"):
        _dummy_hash.value = generate_password_hash("invalid-user")
    return _dummy_hash.value
