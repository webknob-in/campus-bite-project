"""Property 1: Role access matrix.

Feature: campusbite-platform, Property 1: Role access matrix
**Validates: Requirements 3.4, 6.2, 11.11, 29.2, 45.2**
"""

from __future__ import annotations

import re

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.main import app
from tests.factories import make_customer, make_owner, make_partner

CUSTOMER, OWNER, PARTNER = "CUSTOMER", "RESTAURANT_OWNER", "DELIVERY_PARTNER"
ALL_ROLES = (CUSTOMER, OWNER, PARTNER)
PUBLIC = "PUBLIC"
ANY_AUTH = "ANY_AUTH"

HTTP_METHODS = {"get", "post", "put", "patch", "delete"}
DOC_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

# Independently written expectations: (regex on path) -> allowed roles / PUBLIC / ANY_AUTH.
_RULES: list[tuple[re.Pattern[str], object]] = [
    (re.compile(r"^/health$"), PUBLIC),
    (re.compile(r"^/auth/(register|login)$"), PUBLIC),
    (re.compile(r"^/auth/me$"), ANY_AUTH),
    (re.compile(r"^/restaurants(/.*)?$"), PUBLIC),
    (re.compile(r"^/dishes$"), PUBLIC),
    (re.compile(r"^/orders(/.*)?$"), {CUSTOMER}),
    (re.compile(r"^/ai/.*$"), {CUSTOMER}),
    (re.compile(r"^/owner/.*$"), {OWNER}),
    (re.compile(r"^/partner/.*$"), {PARTNER}),
]


def _expected(path: str):
    for pattern, rule in _RULES:
        if pattern.match(path):
            return rule
    return None


def _inventory() -> list[tuple[str, str]]:
    schema = app.openapi()
    return sorted(
        (m.upper(), p)
        for p, item in schema["paths"].items()
        for m in item
        if m in HTTP_METHODS
    )


def _concrete(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "987654", path)


def _allowed(rule: object, role: str) -> bool:
    return rule in (PUBLIC, ANY_AUTH) or role in rule  # type: ignore[operator]


ROUTES = _inventory()
PAIRS = [(m, p, r) for m, p in ROUTES for r in ALL_ROLES]


@pytest.fixture
def tokens(db, auth_headers):
    users = {CUSTOMER: make_customer(db), OWNER: make_owner(db), PARTNER: make_partner(db)}
    db.commit()
    return {role: auth_headers(u) for role, u in users.items()}


def _send(client, method: str, path: str, headers: dict | None):
    kwargs: dict = {"headers": headers or {}}
    if method in {"POST", "PUT", "PATCH"}:
        kwargs["json"] = {}
    return client.request(method, _concrete(path), **kwargs)


def _check(client, tokens, method: str, path: str, caller: str) -> None:
    rule = _expected(path)
    assert rule is not None
    if caller == "none":
        headers = None
    elif caller == "garbage":
        headers = {"Authorization": "Bearer not.a.token"}
    else:
        headers = tokens[caller]
    status = _send(client, method, path, headers).status_code
    where = f"{method} {path} as {caller}: got {status}"
    if rule == PUBLIC:
        assert status not in (401, 403), where
    elif caller in ("none", "garbage"):
        assert status == 401, where
    elif _allowed(rule, caller):
        assert status not in (401, 403), where
    else:
        assert status == 403, where


def test_every_route_is_classified() -> None:
    unclassified = [
        f"{m} {p}" for m, p in ROUTES if p not in DOC_PATHS and _expected(p) is None
    ]
    assert not unclassified, f"Unclassified routes (update the matrix): {unclassified}"
    assert any(_expected(p) not in (None, PUBLIC) for _, p in ROUTES)


def test_role_matrix_exhaustive(client, tokens) -> None:
    for m, p in ROUTES:
        if p in DOC_PATHS:
            continue
        for caller in ("none", "garbage", *ALL_ROLES):
            _check(client, tokens, m, p, caller)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(pair=st.sampled_from([x for x in PAIRS if x[1] not in DOC_PATHS]))
def test_property_role_access_matrix(client, tokens, pair) -> None:
    """Feature: campusbite-platform, Property 1: Role access matrix"""
    method, path, role = pair
    _check(client, tokens, method, path, role)
