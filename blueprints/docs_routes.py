"""OpenAPI document for the metrics endpoint."""

from flask import Blueprint, jsonify

from extensions import cache
from schemas import build_openapi_spec

docs_bp = Blueprint("docs", __name__)


@docs_bp.get("/api/openapi.json")
def openapi():
    spec = cache.get("openapi-spec")
    if spec is None:
        spec = build_openapi_spec()
        cache.set("openapi-spec", spec)
    return jsonify(spec)
