"""AI insights: build a privacy-safe order context and ask OpenAI about the caller's orders.

Only the calling Customer's own Orders are loaded (Req 28.1). The API key and prompts are never
logged; failures log only the exception type name.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timezone
from typing import Any

import openai
from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.core.config import get_settings
from app.core.errors import RateLimitedError, ServiceUnavailableError, UpstreamError
from app.models import Order, User
from app.services.rate_limiter import get_ai_limiter

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are CampusBite's order assistant. Answer ONLY using the JSON order history provided. "
    "If the answer is not in the data, say you don't have that information. "
    "Amounts are in INR. Today's date is given as 'today'. Be concise."
)

SUMMARY_QUESTION = (
    "Summarize my last five orders: which restaurants, what I ordered, the total spent, "
    "and the current status of each."
)
NO_ORDERS_MESSAGE = "You have no orders yet. Place an order and then ask me about it."
ASK_ORDER_LIMIT = 50
SUMMARY_ORDER_LIMIT = 5
DEFAULT_RETRY_AFTER_SECONDS = 20
UPSTREAM_DETAIL = "The AI service is currently unavailable. Please try again later."


def load_customer_orders(db: Session, customer_id: int, limit: int = ASK_ORDER_LIMIT) -> list[Order]:
    """The customer's ``limit`` most recent Orders (items and restaurant loaded), newest first."""
    stmt = (
        select(Order)
        .where(Order.customer_id == customer_id)
        .options(selectinload(Order.items), joinedload(Order.restaurant))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
    )
    return list(db.scalars(stmt).all())


def build_context(orders: list[Order], today: date) -> str:
    """JSON text of the Orders; contains no emails, addresses, phones, card data or other users."""
    return json.dumps(
        {
            "today": today.isoformat(),
            "order_count": len(orders),
            "orders": [
                {
                    "id": o.id,
                    "restaurant": o.restaurant.name,
                    "status": o.status.value,
                    "payment_status": o.payment_status.value,
                    "return_status": o.return_status.value,
                    "total": float(o.total_amount),
                    "created_at": o.created_at.isoformat(),
                    "delivered_at": o.delivered_at.isoformat() if o.delivered_at else None,
                    "items": [
                        {"name": i.name, "qty": i.quantity, "unit_price": float(i.unit_price)}
                        for i in o.items
                    ],
                }
                for o in orders
            ],
        },
        separators=(",", ":"),
    )


def get_openai_client() -> OpenAI:
    """FastAPI dependency. Tests override it with a fake client."""
    key = (get_settings().openai_api_key or "").strip()
    if not key:
        raise ServiceUnavailableError("AI insights are not configured")
    return OpenAI(api_key=key, timeout=30.0, max_retries=2)


def _retry_after(exc: openai.RateLimitError) -> float:
    try:
        value = exc.response.headers.get("retry-after")
        if value is not None:
            seconds = float(value)
            if seconds >= 0:
                return seconds
    except (AttributeError, TypeError, ValueError):
        pass
    return DEFAULT_RETRY_AFTER_SECONDS


def _run(
    db: Session, client: Any, customer: User, question: str, limit: int, now: datetime | None
) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    wait = get_ai_limiter().check(customer.id)
    if wait is not None:
        raise RateLimitedError(wait)

    orders = load_customer_orders(db, customer.id, limit)
    if not orders:
        return {"answer": NO_ORDERS_MESSAGE, "order_count": 0, "generated_at": now}

    context = build_context(orders, now.date())
    try:
        completion = client.chat.completions.create(
            model=get_settings().openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Order history JSON:\n{context}\n\nQuestion: {question}"},
            ],
            temperature=0.2,
            max_tokens=500,
        )
    except openai.RateLimitError as exc:
        logger.warning("OpenAI call failed: %s", type(exc).__name__)
        raise RateLimitedError(_retry_after(exc)) from None
    except openai.OpenAIError as exc:  # timeout, connection, status and any other SDK error
        logger.warning("OpenAI call failed: %s", type(exc).__name__)
        raise UpstreamError(UPSTREAM_DETAIL) from None

    try:
        answer = completion.choices[0].message.content
    except (AttributeError, IndexError, TypeError):
        answer = None
    if not answer or not str(answer).strip():
        logger.warning("OpenAI returned an empty completion")
        raise UpstreamError(UPSTREAM_DETAIL)
    return {"answer": str(answer).strip(), "order_count": len(orders), "generated_at": now}


def ask(
    db: Session, client: Any, customer: User, question: str, now: datetime | None = None
) -> dict[str, Any]:
    return _run(db, client, customer, question, ASK_ORDER_LIMIT, now)


def summarize(
    db: Session, client: Any, customer: User, now: datetime | None = None
) -> dict[str, Any]:
    return _run(db, client, customer, SUMMARY_QUESTION, SUMMARY_ORDER_LIMIT, now)
