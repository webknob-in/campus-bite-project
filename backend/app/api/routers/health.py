"""``GET /health``: liveness plus a database probe (Req 30.6, 40.11)."""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


class HealthOut(BaseModel):
    status: Literal["ok", "error"]
    database: Literal["ok", "error"]


@router.get(
    "/health",
    response_model=HealthOut,
    summary="Service and database health",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": HealthOut,
            "description": "The database query `SELECT 1` failed.",
        }
    },
)
def health(response: Response, db: Session = Depends(get_db)) -> HealthOut:
    """Return 200 when `SELECT 1` succeeds, otherwise 503 (public, no authentication)."""
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # any failure to run the probe means the database is unusable
        logger.warning("Health check failed: %s: %s", type(exc).__name__, exc)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthOut(status="error", database="error")
    return HealthOut(status="ok", database="ok")
