"""JSON metrics resource."""

from flask import current_app
from flask_restful import Resource

import db
from auth import login_required
from blueprints import database_path
from errors import make_error
from present import present
from schemas import dump_metrics
from services.metrics import record_server_metrics


class ServerMetricsResource(Resource):
    """Latest metrics for one server. Session cookie or bearer token."""

    method_decorators = [login_required]

    def get(self, server_id: int):
        server = db.get_server(database_path(), server_id)
        if server is None:
            raise make_error("Server not found.", 404)
        recorded = record_server_metrics(database_path(), server)
        current_app.logger.info("Collected metrics for server %s", server_id)
        return dump_metrics(present(server, recorded["error"], recorded["samples"]))
