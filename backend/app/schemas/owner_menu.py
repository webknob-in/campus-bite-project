"""Request schemas for ``/owner/menu-items`` (Req 16).

Responses use ``MenuItemOut`` from ``app.schemas.menu``.
"""

from decimal import Decimal
from typing import Annotated, Any

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    Field,
    HttpUrl,
    StrictBool,
    StringConstraints,
    TypeAdapter,
)

MAX_PRICE = Decimal("100000")  # Req 16.6: above 100000 is rejected
_HTTP_URL = TypeAdapter(HttpUrl)


def _reject_bool(value: Any) -> Any:
    # ``True`` is an ``int`` in Python and would otherwise be read as the price 1.
    if isinstance(value, bool):
        raise ValueError("Input should be a decimal number, not a boolean")
    return value


def _blank_to_none(value: Any) -> Any:
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _check_http_url(value: str) -> str:
    _HTTP_URL.validate_python(value)  # raises ValidationError (a ValueError) when malformed
    return value


# gt=0, <= 100000, at most 8 digits in total and 2 decimal places. NaN/Infinity are rejected by
# pydantic's Decimal validation; non-numeric text fails to parse.
PriceIn = Annotated[
    Decimal,
    BeforeValidator(_reject_bool),
    Field(gt=0, le=MAX_PRICE, max_digits=8, decimal_places=2),
]
NameIn = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
DescriptionIn = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None,
    BeforeValidator(_blank_to_none),
]
CategoryIn = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)] | None,
    BeforeValidator(_blank_to_none),
]
ImageUrlIn = Annotated[
    Annotated[str, StringConstraints(strip_whitespace=True, max_length=500), AfterValidator(_check_http_url)] | None,
    BeforeValidator(_blank_to_none),
]


class MenuItemCreate(BaseModel):
    name: NameIn
    price: PriceIn
    description: DescriptionIn = None
    category: CategoryIn = None
    image_url: ImageUrlIn = None
    is_available: StrictBool = True


class MenuItemUpdate(BaseModel):
    """Partial update: only the fields present in the body change (``exclude_unset``).

    ``name``, ``price`` and ``is_available`` are not nullable, so an explicit ``null`` for them is a
    422. ``description``, ``category`` and ``image_url`` accept ``null`` to clear the value. The
    ``None`` defaults of the non-nullable fields are never used because unset fields are dropped.
    """

    name: NameIn = Field(default=None)  # type: ignore[assignment]
    price: PriceIn = Field(default=None)  # type: ignore[assignment]
    description: DescriptionIn = None
    category: CategoryIn = None
    image_url: ImageUrlIn = None
    is_available: StrictBool = Field(default=None)  # type: ignore[assignment]


class AvailabilityIn(BaseModel):
    is_available: StrictBool
