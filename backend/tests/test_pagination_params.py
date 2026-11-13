"""DB-free checks for the PageParams dependency bounds (Req 27.1, 27.2, 27.4)."""

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.schemas.common import PageParams

_app = FastAPI()


@_app.get("/echo")
def _echo(params: PageParams = Depends()) -> dict[str, int]:
    return {"page": params.page, "page_size": params.page_size, "offset": params.offset}


_client = TestClient(_app)


def test_defaults() -> None:
    assert _client.get("/echo").json() == {"page": 1, "page_size": 10, "offset": 0}


def test_valid_bounds() -> None:
    assert _client.get("/echo", params={"page": 3, "page_size": 100}).json()["offset"] == 200
    assert _client.get("/echo", params={"page": 1, "page_size": 1}).status_code == 200


@pytest.mark.parametrize(
    "query",
    [{"page": 0}, {"page": -1}, {"page_size": 0}, {"page_size": 101}, {"page": "x"}],
)
def test_out_of_range_is_422(query: dict[str, object]) -> None:
    assert _client.get("/echo", params=query).status_code == 422
