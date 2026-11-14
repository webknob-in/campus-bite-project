"""Route inventory: every endpoint of Requirement 40 exists and list endpoints use the page envelope."""
import re

import pytest

from app.main import app

REQUIRED = [
    ("get", "/health"),
    ("post", "/auth/register"), ("post", "/auth/login"), ("get", "/auth/me"),
    ("get", "/restaurants"), ("get", "/restaurants/{id}"), ("get", "/restaurants/{id}/menu"),
    ("get", "/dishes"), ("get", "/restaurants/{id}/reviews"),
    ("get", "/owner/menu-items"), ("post", "/owner/menu-items"),
    ("patch", "/owner/menu-items/{id}"), ("delete", "/owner/menu-items/{id}"),
    ("patch", "/owner/menu-items/{id}/availability"),
    ("post", "/orders"), ("get", "/orders/me"), ("get", "/orders/{id}"),
    ("post", "/orders/{id}/cancel"), ("post", "/orders/{id}/review"), ("post", "/orders/{id}/return"),
    ("get", "/owner/orders"), ("patch", "/owner/orders/{id}/status"),
    ("get", "/partner/orders"), ("get", "/partner/orders/{id}"),
    ("patch", "/partner/orders/{id}/status"), ("get", "/partner/history"),
    ("get", "/owner/delivery-partners"), ("post", "/owner/orders/{id}/assign"),
    ("get", "/owner/returns"), ("post", "/owner/returns/{id}/approve"),
    ("post", "/owner/returns/{id}/reject"),
    ("post", "/ai/insights"), ("get", "/ai/insights/summary"),
    ("get", "/owner/stats"), ("get", "/owner/reminders"), ("patch", "/owner/reminders/{id}/resolve"),
]

LIST_ENDPOINTS = [
    "/restaurants", "/dishes", "/restaurants/{id}/menu", "/restaurants/{id}/reviews", "/orders/me",
    "/owner/menu-items", "/owner/orders", "/owner/delivery-partners", "/owner/returns",
    "/owner/reminders", "/partner/orders", "/partner/history",
]


def _norm(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "{id}", path)


def _paths():
    return {_norm(p): v for p, v in app.openapi()["paths"].items()}


def _resolve(schema, spec):
    while "$ref" in schema:
        node = spec
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        schema = node
    return schema


@pytest.mark.parametrize("method,path", REQUIRED)
def test_required_route_exists(method, path):
    assert method in _paths().get(path, {}), f"missing {method.upper()} {path}"


@pytest.mark.parametrize("path", LIST_ENDPOINTS)
def test_list_endpoint_uses_page_envelope(path):
    spec = app.openapi()
    op = _paths()[path]["get"]
    schema = _resolve(op["responses"]["200"]["content"]["application/json"]["schema"], spec)
    assert {"items", "total", "page", "page_size"} <= set(schema["properties"])


def test_docs_and_headers(client):
    for p in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(p).status_code == 200
    r = client.get("/health")
    assert r.status_code == 200
    assert r.headers["X-Request-ID"] and "X-Process-Time" in r.headers
