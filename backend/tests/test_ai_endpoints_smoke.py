"""Smoke tests for POST /ai/insights and GET /ai/insights/summary."""

import httpx
import openai
import pytest

from app.main import app
from app.services.ai_service import NO_ORDERS_MESSAGE, get_openai_client
from app.services.rate_limiter import reset_ai_limiter
from tests.factories import make_customer, make_order, make_owner, make_partner


class FakeClient:
    def __init__(self, content="You ordered pizza.", exc=None):
        self.calls = 0
        self._content = content
        self._exc = exc
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        self.calls += 1
        if self._exc:
            raise self._exc
        msg = type("M", (), {"content": self._content})()
        return type("C", (), {"choices": [type("Ch", (), {"message": msg})()]})()


@pytest.fixture(autouse=True)
def _clean():
    reset_ai_limiter()
    yield
    app.dependency_overrides.pop(get_openai_client, None)
    reset_ai_limiter()


def _use(fake):
    app.dependency_overrides[get_openai_client] = lambda: fake
    return fake


def test_post_and_get_happy_path(client, db, auth_headers):
    customer = make_customer(db)
    make_order(db, customer=customer)
    db.commit()
    fake = _use(FakeClient())
    r = client.post("/ai/insights", json={"question": "  what did I order? "}, headers=auth_headers(customer))
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "You ordered pizza." and body["order_count"] == 1 and body["generated_at"]
    r = client.get("/ai/insights/summary", headers=auth_headers(customer))
    assert r.status_code == 200 and r.json()["order_count"] == 1
    assert fake.calls == 2


def test_empty_history_no_call(client, db, auth_headers):
    customer = make_customer(db)
    db.commit()
    fake = _use(FakeClient())
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(customer))
    assert r.status_code == 200
    assert r.json()["answer"] == NO_ORDERS_MESSAGE and r.json()["order_count"] == 0
    assert fake.calls == 0


@pytest.mark.parametrize("q", ["   ", "x" * 501])
def test_invalid_question_422(client, db, auth_headers, q):
    customer = make_customer(db)
    db.commit()
    _use(FakeClient())
    r = client.post("/ai/insights", json={"question": q}, headers=auth_headers(customer))
    assert r.status_code == 422


def test_non_customers_403(client, db, auth_headers):
    owner, partner = make_owner(db), make_partner(db)
    db.commit()
    _use(FakeClient())
    for user in (owner, partner):
        assert client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(user)).status_code == 403
        assert client.get("/ai/insights/summary", headers=auth_headers(user)).status_code == 403


def test_visitor_401_without_key(client):
    assert client.post("/ai/insights", json={"question": "hi"}).status_code == 401
    assert client.get("/ai/insights/summary").status_code == 401


def test_customer_503_without_key(client, db, auth_headers):
    customer = make_customer(db)
    db.commit()
    r = client.post("/ai/insights", json={"question": "hi"}, headers=auth_headers(customer))
    assert r.status_code == 503
    assert client.get("/ai/insights/summary", headers=auth_headers(customer)).status_code == 503


def test_sixth_call_429_with_retry_after(client, db, auth_headers):
    customer = make_customer(db)
    make_order(db, customer=customer)
    db.commit()
    _use(FakeClient())
    h = auth_headers(customer)
    for _ in range(5):
        assert client.post("/ai/insights", json={"question": "hi"}, headers=h).status_code == 200
    r = client.post("/ai/insights", json={"question": "hi"}, headers=h)
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) >= 1


def test_upstream_error_502(client, db, auth_headers):
    customer = make_customer(db)
    make_order(db, customer=customer)
    db.commit()
    exc = openai.APIConnectionError(request=httpx.Request("POST", "https://api.openai.com/v1"))
    _use(FakeClient(exc=exc))
    r = client.get("/ai/insights/summary", headers=auth_headers(customer))
    assert r.status_code == 502
