"""Domain exceptions and the handlers that turn them into ``{"detail": ...}`` responses.

Services and dependencies raise these exceptions; ``register_exception_handlers``
maps each one to its HTTP status code (Req 41.3, 41.4). Pydantic validation errors
(422) and Starlette ``HTTPException`` (unknown route, wrong method) already produce a
``{"detail": ...}`` body through FastAPI's default handlers.
"""

import math
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class DomainError(Exception):
    """Base class for errors that map to an HTTP response with a ``detail`` body."""

    status_code: int = 500
    default_detail: str = "Internal server error"

    def __init__(self, detail: str | None = None, headers: Mapping[str, str] | None = None) -> None:
        self.detail = detail if detail is not None else self.default_detail
        self.headers: dict[str, str] = dict(headers) if headers else {}
        super().__init__(self.detail)


class BadRequestError(DomainError):
    """400: business-rule violation in the request content."""

    status_code = 400
    default_detail = "Bad request"


class UnauthorizedError(DomainError):
    """401: missing/invalid/expired JWT or bad credentials."""

    status_code = 401
    default_detail = "Not authenticated"

    def __init__(self, detail: str | None = None, headers: Mapping[str, str] | None = None) -> None:
        merged = {"WWW-Authenticate": "Bearer"}
        if headers:
            merged.update(headers)
        super().__init__(detail, merged)


class ForbiddenError(DomainError):
    """403: the User's Role is not allowed to perform the action."""

    status_code = 403
    default_detail = "You do not have permission for this action"


class NotFoundError(DomainError):
    """404: the resource does not exist or belongs to another tenant."""

    status_code = 404
    default_detail = "Not found"


class ConflictError(DomainError):
    """409: the request conflicts with the current state of the resource."""

    status_code = 409
    default_detail = "Conflict"


class InvalidTransitionError(ConflictError):
    """409: the requested Order_Status change is not allowed."""

    default_detail = "Invalid status transition"


class RateLimitedError(DomainError):
    """429: AI rate limit or OpenAI rate limit; sets ``Retry-After`` (whole seconds)."""

    status_code = 429
    default_detail = "Too many requests"

    def __init__(self, retry_after: float | int, detail: str | None = None) -> None:
        # Retry-After must be a non-negative integer number of seconds; round up so the
        # client never retries before the slot frees.
        seconds = max(0, math.ceil(retry_after))
        self.retry_after = seconds
        super().__init__(
            detail if detail is not None else f"Too many requests. Try again in {seconds} seconds.",
            {"Retry-After": str(seconds)},
        )


class UpstreamError(DomainError):
    """502: the upstream OpenAI call failed or timed out."""

    status_code = 502
    default_detail = "Upstream service error"


class ServiceUnavailableError(DomainError):
    """503: a dependency (AI key, database) is unavailable."""

    status_code = 503
    default_detail = "Service unavailable"


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers or None,
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Safety net so a 500 is always JSON with a generic body (Req 41.4). The request
    # middleware normally catches unhandled errors first and logs them with the request id.
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(DomainError, domain_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_error_handler)
