"""Local demo for Linux server CPU, memory, network, and listening ports."""

import logging
import os
import secrets

from flask import Flask, request, session
from flask_restful import Api
from flasgger import Swagger

import db
from blueprints.auth_routes import auth_bp
from blueprints.docs_routes import docs_bp
from blueprints.metrics_routes import ServerMetricsResource
from blueprints.server_routes import servers_bp
from config import apply_config
from errors import register_error_handlers
from extensions import init_extensions
from present import status_class
from schemas import build_swagger_template


def create_app(test_config: dict | None = None) -> Flask:
    _load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    app = Flask(__name__)
    apply_config(app, test_config)
    _configure_logging(app)
    init_extensions(app)
    db.init_db(app.config["DATABASE"])
    _register_hooks(app)
    register_error_handlers(app)
    app.register_blueprint(auth_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(docs_bp)
    api = Api(app)
    api.add_resource(
        ServerMetricsResource,
        "/servers/<int:server_id>/metrics",
        endpoint="server_metrics",
    )
    Swagger(app, template=build_swagger_template())
    return app


def _register_hooks(app: Flask) -> None:
    @app.before_request
    def ensure_csrf() -> None:
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_urlsafe(32)

    @app.before_request
    def log_mutation() -> None:
        if request.method == "POST":
            app.logger.info("%s %s", request.method, request.path)

    @app.after_request
    def secure_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.teardown_request
    def log_request_failure(error) -> None:
        if error is not None:
            app.logger.error("Request ended with an error")

    @app.context_processor
    def inject_globals():
        return {
            "csrf_token": session.get("csrf_token", ""),
            "current_user": session.get("username"),
            "status_class": status_class,
        }


def _configure_logging(app: Flask) -> None:
    if app.testing:
        app.logger.setLevel(logging.ERROR)
        return
    app.logger.setLevel(logging.INFO)


def _load_dotenv(path: str) -> None:
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
