"""Error types and HTTP error handlers."""

from flask import Flask, jsonify, render_template, request


class AppError(Exception):
    """Request error with a status code and a message safe to show the user."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def make_error(message: str, status_code: int = 400) -> AppError:
    return AppError(message, status_code)


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(AppError)
    def handle_app_error(error: AppError):
        app.logger.info("Application error: %s", error.message)
        if request.path.endswith("/metrics"):
            return jsonify({"ok": False, "error": error.message}), error.status_code
        return render_template("error.html", message=error.message), error.status_code

    @app.errorhandler(400)
    def bad_request(_error):
        return render_template("error.html", message="Invalid request."), 400

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("error.html", message="Page not found."), 404
