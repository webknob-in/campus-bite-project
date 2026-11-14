"""AI order insights for customers (Req 28, 29.2, 40.9)."""

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models import Role, User
from app.schemas.ai import AIAnswerOut, AIQuestionIn
from app.services import ai_service

router = APIRouter(prefix="/ai", tags=["ai"])

_RESPONSES = {
    401: {"description": "Missing or invalid token."},
    403: {"description": "Not a CUSTOMER."},
    429: {"description": "Rate limited; see the Retry-After header."},
    502: {"description": "The AI provider failed."},
    503: {"description": "AI insights are not configured."},
}

require_customer = require_roles(Role.CUSTOMER)


def get_client(
    _user: User = Depends(require_customer),
    client: Any = Depends(ai_service.get_openai_client),
) -> Any:
    """Resolve the OpenAI client only after the caller is an authorised customer."""
    return client


@router.post(
    "/insights",
    response_model=AIAnswerOut,
    summary="Ask a question about my orders",
    responses={**_RESPONSES, 422: {"description": "Question is blank or longer than 500 characters."}},
)
def ask_insights(
    body: AIQuestionIn,
    user: User = Depends(require_customer),
    client: Any = Depends(get_client),
    db: Session = Depends(get_db),
) -> dict:
    return ai_service.ask(db, client, user, body.question)


@router.get(
    "/insights/summary",
    response_model=AIAnswerOut,
    summary="Summarize my last five orders",
    responses=_RESPONSES,
)
def insights_summary(
    user: User = Depends(require_customer),
    client: Any = Depends(get_client),
    db: Session = Depends(get_db),
) -> dict:
    return ai_service.summarize(db, client, user)
