"""Environment configuration for development, testing, and production."""

import os
from datetime import timedelta

DEV_SECRET_KEY = "dev-only-local-key"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SHARED_CONFIG = {
    "DEBUG": False,
    "SESSION_COOKIE_HTTPONLY": True,
    "SESSION_COOKIE_SAMESITE": "Lax",
    "JWT_TOKEN_LOCATION": ["headers"],
    "JWT_ACCESS_TOKEN_EXPIRES": timedelta(hours=12),
    "CACHE_TYPE": "SimpleCache",
    "CACHE_DEFAULT_TIMEOUT": 300,
    "ERROR_404_HELP": False,
}


def select_config_name(test_config: dict | None) -> str:
    if test_config and test_config.get("TESTING"):
        return "testing"
    name = os.environ.get("APP_ENV", "development").strip().lower()
    if name in {"development", "testing", "production"}:
        return name
    return "development"


def apply_config(app, test_config: dict | None) -> None:
    config_name = select_config_name(test_config)
    app.config.from_mapping(SHARED_CONFIG)
    app.config["APP_ENV"] = config_name
    app.config["TESTING"] = config_name == "testing"
    secret = os.environ.get("SECRET_KEY")
    if config_name == "production" and not secret:
        raise RuntimeError("SECRET_KEY is required when APP_ENV=production")
    app.config["SECRET_KEY"] = secret or DEV_SECRET_KEY
    app.config["JWT_SECRET_KEY"] = app.config["SECRET_KEY"]
    app.config["DATABASE"] = os.environ.get("DATABASE") or os.path.join(BASE_DIR, "monitor.db")
    if not test_config:
        return
    app.config.update(test_config)
    if "SECRET_KEY" in test_config:
        app.config["JWT_SECRET_KEY"] = test_config["SECRET_KEY"]
