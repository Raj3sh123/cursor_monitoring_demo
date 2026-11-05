"""Route blueprints for the monitoring app."""

from flask import current_app


def database_path() -> str:
    return current_app.config["DATABASE"]
