"""Smoke tests for app.services.ai_service using a fake OpenAI client."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.config import get_settings
from app.core.errors import RateLimitedError, ServiceUnavailableError, UpstreamError
from app.services import ai_service
from app.services.rate_limiter import reset_ai_limiter
from tests.factories import make_customer, make_order


class FakeOpenAI:
    def __init__(self, content: str | None = "Fake answer", error: Exception | None = None):
        self.calls: list[dict] = []
        self._content = content
        self._error = error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _response(status: int, headers: dict | None = None) -> httpx.Response:
    return httpx.Response(status, headers=headers, request=httpx.Request("POST", "https://x/y"))


@pytest.fixture(autouse=True)
def _limiter():
    reset_ai_limiter()
    yield
    reset_ai_limiter()


def _context_of(call: dict) -> dict:
    text = call["messages"][1]["content"]
    start = text.index("{")
    end = text.rindex("}") + 1
    return json.loads(text[start:end])


def test_ask_happy_path_sends_system_prompt_and_model(db):
    c = make_customer(db)
    o = make_order(db, customer=c)
    fake = FakeOpenAI()
    out = ai_service.ask(db, fake, c, "What did I order?")
    assert out["answer"] == "Fake answer" and out["order_count"] == 1
    call = fake.calls[0]
    assert call["model"] == get_settings().openai_model
    assert call["messages"][0] == {"role": "system", "content": ai_service.SYSTEM_PROMPT}
    assert "Amounts are in INR" in call["messages"][0]["content"]
    assert "What did I order?" in call["messages"][1]["content"]
    assert [x["id"] for x in _context_of(call)["orders"]] == [o.id]


def test_empty_history_does_not_call_openai(db):
    c = make_customer(db)
    fake = FakeOpenAI()
    out = ai_service.ask(db, fake, c, "hi")
    assert out["answer"] == ai_service.NO_ORDERS_MESSAGE and out["order_count"] == 0
    assert fake.calls == []


def test_other_customers_orders_absent(db):
    a, b = make_customer(db), make_customer(db)
    mine = make_order(db, customer=a)
    theirs = make_order(db, customer=b)
    fake = FakeOpenAI()
    ai_service.ask(db, fake, a, "q")
    ids = [x["id"] for x in _context_of(fake.calls[0])["orders"]]
    assert ids == [mine.id] and theirs.id not in ids
    assert b.email not in fake.calls[0]["messages"][1]["content"]


def test_limiter_blocks_sixth_call(db):
    c = make_customer(db)
    make_order(db, customer=c)
    fake = FakeOpenAI()
    now = datetime.now(timezone.utc)
    for _ in range(5):
        ai_service.ask(db, fake, c, "q", now=now)
    with pytest.raises(RateLimitedError) as ei:
        ai_service.ask(db, fake, c, "q", now=now)
    assert ei.value.headers["Retry-After"]
    assert len(fake.calls) == 5


def test_error_mappings(db, monkeypatch):
    monkeypatch.setattr(get_settings(), 'ai_rate_limit_per_minute', 100, raising=False)
    c = make_customer(db)
    make_order(db, customer=c)
    req = httpx.Request("POST", "https://x/y")
    with pytest.raises(RateLimitedError) as ei:
        ai_service.ask(
            db,
            FakeOpenAI(error=openai.RateLimitError("x", response=_response(429, {"retry-after": "7"}), body=None)),
            c,
            "q",
        )
    assert ei.value.retry_after == 7
    with pytest.raises(RateLimitedError) as ei:
        ai_service.ask(db, FakeOpenAI(error=openai.RateLimitError("x", response=_response(429), body=None)), c, "q")
    assert ei.value.retry_after == ai_service.DEFAULT_RETRY_AFTER_SECONDS
    for err in (
        openai.APITimeoutError(request=req),
        openai.APIConnectionError(request=req),
        openai.InternalServerError("x", response=_response(500), body=None),
    ):
        with pytest.raises(UpstreamError):
            ai_service.ask(db, FakeOpenAI(error=err), c, "q")
    for empty in (None, "  "):
        with pytest.raises(UpstreamError):
            ai_service.ask(db, FakeOpenAI(content=empty), c, "q")


def test_summarize_uses_at_most_five_newest_orders(db):
    c = make_customer(db)
    base = datetime.now(timezone.utc) - timedelta(days=10)
    orders = [make_order(db, customer=c, created_at=base + timedelta(hours=i)) for i in range(7)]
    fake = FakeOpenAI()
    out = ai_service.summarize(db, fake, c)
    assert out["order_count"] == 5
    ids = [x["id"] for x in _context_of(fake.calls[0])["orders"]]
    assert ids == [o.id for o in reversed(orders[2:])]


def test_context_round_trip_and_no_pii(db):
    c = make_customer(db)
    o = make_order(db, customer=c)
    ctx = json.loads(ai_service.build_context(ai_service.load_customer_orders(db, c.id), datetime.now().date()))
    assert ctx["orders"][0]["total"] == float(o.total_amount)
    raw = json.dumps(ctx)
    assert o.delivery_address not in raw and o.delivery_phone not in raw and c.password_hash not in raw


def test_client_dependency_503_without_key(monkeypatch):
    monkeypatch.setattr(ai_service, "get_settings", lambda: SimpleNamespace(openai_api_key="  "))
    with pytest.raises(ServiceUnavailableError) as ei:
        ai_service.get_openai_client()
    assert ei.value.detail == "AI insights are not configured"
    monkeypatch.setattr(ai_service, "get_settings", lambda: SimpleNamespace(openai_api_key="sk-secret-123"))
    assert ai_service.get_openai_client().timeout == 30.0


def test_key_and_prompt_not_logged(db, caplog, monkeypatch):
    c = make_customer(db)
    make_order(db, customer=c)
    req = httpx.Request("POST", "https://x/y")
    real = get_settings()
    monkeypatch.setattr(real, "openai_api_key", "sk-secret-123", raising=False)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(UpstreamError):
            ai_service.ask(db, FakeOpenAI(error=openai.APITimeoutError(request=req)), c, "secret question")
    text = caplog.text
    assert "APITimeoutError" in text
    assert "sk-secret-123" not in text and "secret question" not in text

