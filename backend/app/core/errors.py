"""One error shape for the whole API: {"error": {"code": ..., "message": ...}}.

The frontend translates by `code`; `message` is an English fallback only.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "NOT_AUTHENTICATED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    415: "UNSUPPORTED_MEDIA_TYPE",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
}


SESSION_COOKIE = "hf_session"
logger = logging.getLogger("helio.errors")


class ApiError(Exception):
    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        details: list | None = None,
        clear_session: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.details = details
        self.clear_session = clear_session


def error_body(code: str, message: str, details: list | None = None) -> dict:
    body: dict = {"code": code, "message": message}
    if details:
        body["details"] = details
    return {"error": body}


def error_response(
    status: int, code: str, message: str, details: list | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status, content=error_body(code, message, details))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        response = error_response(exc.status, exc.code, exc.message, exc.details)
        if exc.clear_session:
            response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = STATUS_CODES.get(exc.status_code, "ERROR")
        message = exc.detail if isinstance(exc.detail, str) else code
        return error_response(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        # Field paths and error types only — never echo submitted values (passwords, PII).
        details = [
            {"field": ".".join(str(p) for p in err["loc"][1:]), "type": err["type"]}
            for err in exc.errors()
        ]
        return error_response(422, "VALIDATION_ERROR", "Some fields are invalid.", details)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log type + path only: exception text can contain user input or personal data.
        logger.error(
            "unhandled %s on %s %s",
            type(exc).__name__,
            request.method,
            request.url.path,
            exc_info=exc,
        )
        return error_response(500, "INTERNAL_ERROR", "Something went wrong.")
