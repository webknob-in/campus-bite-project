"""Shared response/request schemas used by every list endpoint (Req 27)."""

from typing import Annotated, Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel

T = TypeVar("T")

MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 10


class Page(BaseModel, Generic[T]):
    """Paginated envelope: ``{items, total, page, page_size}`` (Req 27.3)."""

    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    """FastAPI dependency parsing ``page`` and ``page_size`` query parameters.

    ``page`` must be >= 1 (default 1) and ``page_size`` must be 1-100 (default 10);
    any other value is rejected with HTTP 422 by FastAPI's query validation
    (Req 27.1, 27.2, 27.4). Use as ``params: PageParams = Depends()``.
    """

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="1-based page number")] = 1,
        page_size: Annotated[
            int, Query(ge=1, le=MAX_PAGE_SIZE, description="Items per page (1-100)")
        ] = DEFAULT_PAGE_SIZE,
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def __repr__(self) -> str:
        return f"PageParams(page={self.page}, page_size={self.page_size})"
