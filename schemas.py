"""Marshmallow schemas for form input and metrics responses."""

from marshmallow import Schema, ValidationError, fields, validates

from collector import is_valid_ip

NAME_MAX_LENGTH = 64


class ServerFormSchema(Schema):
    name = fields.String(required=True)
    ip = fields.String(required=True)

    @validates("name")
    def validate_name(self, value: str) -> None:
        if not value or len(value) > NAME_MAX_LENGTH:
            raise ValidationError(f"Name must be 1 to {NAME_MAX_LENGTH} characters.")

    @validates("ip")
    def validate_ip(self, value: str) -> None:
        if not is_valid_ip(value):
            raise ValidationError("Enter a valid IP address.")


class ServerSchema(Schema):
    id = fields.Integer(required=True)
    name = fields.String(required=True)
    ip = fields.String(required=True)


class MemorySchema(Schema):
    percent = fields.Float(allow_none=True)
    percent_display = fields.String()
    used_display = fields.String()
    total_display = fields.String()
    available_display = fields.String()


class NetworkRowSchema(Schema):
    iface = fields.String()
    rx_display = fields.String()
    tx_display = fields.String()
    rx_rate_display = fields.String()
    tx_rate_display = fields.String()


class PortSchema(Schema):
    proto = fields.String()
    address = fields.String()
    port = fields.Integer()


class HistorySchema(Schema):
    labels = fields.List(fields.String())
    cpu = fields.List(fields.Float(allow_none=True))
    memory = fields.List(fields.Float(allow_none=True))


class MetricsResponseSchema(Schema):
    ok = fields.Boolean(required=True)
    error = fields.String(allow_none=True)
    server = fields.Nested(ServerSchema)
    collected_at = fields.String(allow_none=True)
    cpu_percent = fields.Float(allow_none=True)
    cpu_display = fields.String()
    memory = fields.Nested(MemorySchema)
    network = fields.List(fields.Nested(NetworkRowSchema))
    ports = fields.List(fields.Nested(PortSchema))
    alert = fields.Boolean()
    status = fields.String()
    history = fields.Nested(HistorySchema)
    refresh_ms = fields.Integer()


def parse_server_form(form: dict) -> dict:
    """Validate a server form and return the cleaned values or an error."""
    name = (form.get("name") or "").strip()
    ip = (form.get("ip") or "").strip()
    try:
        loaded = ServerFormSchema().load({"name": name, "ip": ip})
    except ValidationError as exc:
        return {
            "is_valid": False,
            "name": name,
            "ip": ip,
            "error": _first_message(exc.messages),
        }
    return {"is_valid": True, "name": loaded["name"], "ip": loaded["ip"], "error": None}


def dump_metrics(payload: dict) -> dict:
    return MetricsResponseSchema().dump(payload)


def build_swagger_template() -> dict:
    return {
        "swagger": "2.0",
        "info": {
            "title": "Server Monitor",
            "version": "1.0.0",
            "description": "Metrics for registered servers. No secrets are documented here.",
        },
        "securityDefinitions": {
            "Bearer": {"type": "apiKey", "name": "Authorization", "in": "header"}
        },
        "paths": {
            "/servers/{server_id}/metrics": {
                "get": {
                    "summary": "Latest metrics for one server",
                    "produces": ["application/json"],
                    "security": [{"Bearer": []}],
                    "parameters": [
                        {
                            "name": "server_id",
                            "in": "path",
                            "required": True,
                            "type": "integer",
                        }
                    ],
                    "responses": {
                        "200": {"description": "Metrics for that server"},
                        "401": {"description": "Authentication required"},
                        "404": {"description": "Server not found"},
                    },
                }
            }
        },
    }


def build_openapi_spec() -> dict:
    return {
        "openapi": "3.0.3",
        "info": {
            "title": "Server Monitor",
            "version": "1.0.0",
            "description": "Session or bearer-token access to one server's metrics.",
        },
        "paths": {
            "/servers/{server_id}/metrics": {
                "get": {
                    "summary": "Latest metrics for one server",
                    "security": [{"bearerAuth": []}],
                    "parameters": [
                        {
                            "name": "server_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "integer"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Metrics for that server"},
                        "401": {"description": "Authentication required"},
                        "404": {"description": "Server not found"},
                    },
                }
            }
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            }
        },
    }


def _first_message(messages: dict) -> str:
    for value in messages.values():
        if isinstance(value, list) and value:
            return str(value[0])
        if isinstance(value, str):
            return value
    return "Invalid request."
