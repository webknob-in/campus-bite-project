"""Request middleware: request id, timing, access log, and the unhandled-error safety net.

Requirements 30.1, 30.2, 30.3, 30.5.
"""

import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

logger = logging.getLogger(__name__)

REQUEST_ID_HEADER = "X-Request-ID"
PROCESS_TIME_HEADER = "X-Process-Time"

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")


def _loggable(value: str) -> str:
    """Escape control characters so a client-supplied path or id cannot forge log lines."""
    return _CONTROL_CHARS.sub(lambda m: f"\\x{ord(m.group()):02x}", value)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id and timing to every response and log one line per request.

    * ``X-Request-ID``: echoes the incoming header, or a generated UUID4 when absent.
      The value is also stored on ``request.state.request_id``.
    * ``X-Process-Time``: handler duration in milliseconds, two decimals.
    * An unhandled exception is logged with its traceback and request id, and turned
      into ``500 {"detail": "Internal server error"}``. The response is built here (not
      by Starlette's outer error handler) so it still passes back through the CORS
      middleware, which must wrap this one, and carries the request-id headers.

    Only the path is logged, never the query string, because query strings can hold
    secrets.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid4())
        request.state.request_id = request_id
        path = _loggable(request.url.path)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled error request_id=%s %s %s",
                _loggable(request_id),
                request.method,
                path,
            )
            response = JSONResponse({"detail": "Internal server error"}, status_code=500)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers[PROCESS_TIME_HEADER] = f"{duration_ms:.2f}"
        response.headers[REQUEST_ID_HEADER] = request_id
        logger.info(
            "%s %s -> %s in %.2fms request_id=%s",
            request.method,
            path,
            response.status_code,
            duration_ms,
            _loggable(request_id),
        )
        return response
