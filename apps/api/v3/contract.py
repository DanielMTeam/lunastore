from http import HTTPStatus

from django.http import JsonResponse
from rest_framework import exceptions
from rest_framework.views import exception_handler

from apps.api.exceptions import LunaException


PROBLEM_JSON = "application/problem+json"


def problem(status, *, code=None, detail=None):
    title = HTTPStatus(status).phrase
    return {
        "type": "about:blank",
        "title": title,
        "status": status,
        "detail": detail or title,
        "code": code or title.lower().replace(" ", "_"),
    }


def problem_response(status, **kwargs):
    return JsonResponse(problem(status, **kwargs), status=status, content_type=PROBLEM_JSON)


def field_errors(errors, path=()):
    if isinstance(errors, dict):
        for key, value in errors.items():
            yield from field_errors(value, (*path, str(key)))
    elif isinstance(errors, list):
        for index, value in enumerate(errors):
            nested = isinstance(value, (list, dict))
            yield from field_errors(value, (*path, str(index)) if nested else path)
    else:
        yield {"path": ".".join(path), "code": getattr(errors, "code", "invalid"), "message": str(errors)}


def v3_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    detail = response.data.get("detail") if isinstance(response.data, dict) else None
    codes = exc.get_codes() if isinstance(exc, exceptions.APIException) else None
    code = codes if isinstance(codes, str) else None
    if isinstance(response.data, dict) and isinstance(response.data.get("code"), str):
        code = str(response.data["code"])
    if isinstance(exc, LunaException):
        code = f"luna_{exc.code}"
    if isinstance(exc, exceptions.ValidationError):
        code = "validation_error"
    response.data = problem(response.status_code, code=code, detail=str(detail) if detail else None)
    if isinstance(exc, exceptions.ValidationError):
        response.data["errors"] = list(field_errors(exc.detail))
    response.content_type = PROBLEM_JSON
    return response


class V3ContractMixin:
    def get_exception_handler(self):
        return v3_exception_handler


class SearchUnavailable(exceptions.APIException):
    status_code = 503
    default_detail = "Search is temporarily unavailable."
    default_code = "search_unavailable"
