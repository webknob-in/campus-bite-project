"""Error-handling unit tests for the AI insights endpoints (fake OpenAI client)."""

import logging
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.config import get_settings
from app.main import app
from app.services import ai_service
from app.services.ai_service import NO_ORDERS_MESSAGE, get_openai_client
from app.services.rate_limiter import reset_ai_limiter
from tests.factories import make_customer, make_order, make_owner, make_partner

SECRET = "sk-secret-key-98765"
UPSTREAM_MSG = "upstream-internal-detail-xyz"
REQ = httpx.Request("POST", "https://x/y")


class FakeClient:
    def __init__(self, content="An answer.", exc=None):
        self.calls: list[dict] = []
        self._content = content
        self._exc = exc
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        if self._exc:
            raise self._exc
        msg = SimpleNamespace(content=self._content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def _resp(status, headers=None):
    return httpx.Response(status, headers=headers, request=REQ)


@pytest.fixture(autouse=True)
def _clean():
    reset_ai_limiter()
    yield
    app.dependency_overrides.pop(get_openai_client, None)
    reset_ai_limiter()


def _use(fake):
    app.dependency_overrides[get_openai_client] = lambda: fake
    return fake


def _customer_with_order(db):
    c = make_customer(db)
    make_order(db, customer=c)
    db.commit()
    return c


@pytest.mark.parametrize("key", ["", "   "])
def test_missing_key_503(client, db, auth_headers, monkeypatch, key):
    c = make_customer(db)
    db.commit()
    monkeypatch.setattr(ai_service, "get_settings", lambda: SimpleNamespace(openai_api_key=key))
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(c))
    assert r.status_code == 503
    assert "AI insights are not configured" in r.text


@pytest.mark.parametrize("retry_after", ["7", None])
def test_rate_limit_error_429_retry_after(client, db, auth_headers, retry_after):
    c = _customer_with_order(db)
    headers = {"retry-after": retry_after} if retry_after else None
    exc = openai.RateLimitError(UPSTREAM_MSG, response=_resp(429, headers), body=None)
    _use(FakeClient(exc=exc))
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(c))
    assert r.status_code == 429
    expected = retry_after or str(ai_service.DEFAULT_RETRY_AFTER_SECONDS)
    assert r.headers["Retry-After"] == expected
    assert UPSTREAM_MSG not in r.text


@pytest.mark.parametrize(
    "exc",
    [
        openai.APITimeoutError(request=REQ),
        openai.APIConnectionError(request=REQ),
        openai.InternalServerError(UPSTREAM_MSG, response=_resp(500), body=None),
        openai.AuthenticationError(UPSTREAM_MSG + SECRET, response=_resp(401), body=None),
    ],
)
def test_upstream_errors_502_generic(client, db, auth_headers, exc):
    c = _customer_with_order(db)
    _use(FakeClient(exc=exc))
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(c))
    assert r.status_code == 502
    assert UPSTREAM_MSG not in r.text and SECRET not in r.text


@pytest.mark.parametrize("content", [None, "   "])
def test_empty_completion_502(client, db, auth_headers, content):
    c = _customer_with_order(db)
    _use(FakeClient(content=content))
    r = client.get("/ai/insights/summary", headers=auth_headers(c))
    assert r.status_code == 502


def test_sixth_request_429_without_calling_fake(client, db, auth_headers):
    c = _customer_with_order(db)
    fake = _use(FakeClient())
    h = auth_headers(c)
    for _ in range(5):
        assert client.post("/ai/insights", json={"question": "hi"}, headers=h).status_code == 200
    r = client.post("/ai/insights", json={"question": "hi"}, headers=h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert len(fake.calls) == 5


def test_each_user_has_own_limit(client, db, auth_headers):
    a, b = _customer_with_order(db), _customer_with_order(db)
    fake = _use(FakeClient())
    for _ in range(5):
        assert client.post("/ai/insights", json={"question": "q"}, headers=auth_headers(a)).status_code == 200
    assert client.post("/ai/insights", json={"question": "q"}, headers=auth_headers(a)).status_code == 429
    assert client.post("/ai/insights", json={"question": "q"}, headers=auth_headers(b)).status_code == 200
    assert len(fake.calls) == 6


def test_no_orders_fixed_message_fake_not_called(client, db, auth_headers):
    c = make_customer(db)
    db.commit()
    fake = _use(FakeClient())
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(c))
    assert r.status_code == 200 and r.json()["answer"] == NO_ORDERS_MESSAGE
    r = client.get("/ai/insights/summary", headers=auth_headers(c))
    assert r.status_code == 200 and r.json()["answer"] == NO_ORDERS_MESSAGE
    assert fake.calls == []


def test_owner_partner_403_visitor_401(client, db, auth_headers):
    owner, partner = make_owner(db), make_partner(db)
    db.commit()
    fake = _use(FakeClient())
    for user in (owner, partner):
        assert client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(user)).status_code == 403
        assert client.get("/ai/insights/summary", headers=auth_headers(user)).status_code == 403
    assert client.post("/ai/insights", json={"question": "hi"}).status_code == 401
    assert client.get("/ai/insights/summary").status_code == 401
    assert fake.calls == []


@pytest.mark.parametrize("q", ["", "   ", "x" * 501])
def test_invalid_question_422(client, db, auth_headers, q):
    c = _customer_with_order(db)
    fake = _use(FakeClient())
    r = client.post("/ai/insights", json={"question": q}, headers=auth_headers(c))
    assert r.status_code == 422
    assert fake.calls == []


def test_captured_call_has_prompt_and_model_without_key(client, db, auth_headers, monkeypatch):
    c = _customer_with_order(db)
    monkeypatch.setattr(get_settings(), "openai_api_key", SECRET, raising=False)
    fake = _use(FakeClient())
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(c))
    assert r.status_code == 200
    call = fake.calls[0]
    assert call["model"] == get_settings().openai_model
    assert call["messages"][0] == {"role": "system", "content": ai_service.SYSTEM_PROMPT}
    assert SECRET not in repr(call)


def test_logs_error_type_only(client, db, auth_headers, caplog, monkeypatch):
    c = _customer_with_order(db)
    monkeypatch.setattr(get_settings(), "openai_api_key", SECRET, raising=False)
    exc = openai.InternalServerError(UPSTREAM_MSG, response=_resp(500), body=None)
    _use(FakeClient(exc=exc))
    with caplog.at_level(logging.DEBUG):
        r = client.post("/ai/insights", json={"question": "private question"}, headers=auth_headers(c))
    assert r.status_code == 502
    assert "InternalServerError" in caplog.text
    assert SECRET not in caplog.text and UPSTREAM_MSG not in caplog.text
    assert "private question" not in caplog.text
