from http import HTTPStatus

from drf_spectacular.contrib.rest_framework_simplejwt import SimpleJWTScheme

from apps.api.v3.contract import PROBLEM_JSON


class LunaJWTScheme(SimpleJWTScheme):
    target_class = "apps.api.authentication.CustomJWTAuthentication"


def document_v3_problems(result, **kwargs):
    paths = result.get("paths", {})
    operations = [
        (path, operation)
        for path, methods in paths.items()
        if path.startswith("/v3/") and path != "/v3/health/"
        for operation in methods.values()
    ]
    if not operations:
        return result

    schemas = result.setdefault("components", {}).setdefault("schemas", {})
    schemas["V3Problem"] = {
        "type": "object",
        "required": ["type", "title", "status", "detail", "code"],
        "properties": {
            "type": {"type": "string", "format": "uri-reference"},
            "title": {"type": "string"},
            "status": {"type": "integer"},
            "detail": {"type": "string"},
            "code": {"type": "string"},
            "errors": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["path", "code", "message"],
                    "properties": {key: {"type": "string"} for key in ("path", "code", "message")},
                },
            },
        },
    }
    for path, operation in operations:
        responses = operation["responses"]
        for status in (400, 401, 403, 404, 429, 500, 503):
            if status == 503 and not path.startswith(("/v3/apps/", "/v3/users/", "/v3/search/", "/v3/me/notifications/", "/v3/auth/", "/v3/batch/")):
                continue
            response = responses.setdefault(str(status), {"description": HTTPStatus(status).phrase})
            response.setdefault("content", {})[PROBLEM_JSON] = {"schema": {"$ref": "#/components/schemas/V3Problem"}}
            header = {401: "WWW-Authenticate", 429: "Retry-After"}.get(status)
            if header:
                response.setdefault("headers", {})[header] = {"schema": {"type": "string"}}
    return result
