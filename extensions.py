"""Shared Flask extensions, initialized once per application."""

from flask_caching import Cache
from flask_jwt_extended import JWTManager

cache = Cache()
jwt = JWTManager()


def init_extensions(app) -> None:
    jwt.init_app(app)
    cache.init_app(app)
