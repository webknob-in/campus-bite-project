"""Request and response schemas for ``/auth`` (Req 4, 5, 41)."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    StringConstraints,
    model_validator,
)

from app.models.enums import Role

PHONE_PATTERN = r"^[0-9+\-\s]{7,20}$"


def _lowercase(value: str) -> str:
    return value.lower()


# EmailStr validates the format and normalises the domain; the whole address is lowercased so
# "A@B.com" and "a@b.com" are the same account (stored and compared lowercased).
LowerEmail = Annotated[EmailStr, AfterValidator(_lowercase)]
Trimmed = StringConstraints(strip_whitespace=True)


class RestaurantIn(BaseModel):
    """Restaurant details supplied by a RESTAURANT_OWNER at registration (Req 4.3)."""

    name: Annotated[str, Trimmed, Field(min_length=2, max_length=120)]
    description: Annotated[str, Trimmed, Field(min_length=1, max_length=1000)]
    cuisine: Annotated[str, Trimmed, Field(min_length=2, max_length=60)]
    address: Annotated[str, Trimmed, Field(min_length=5, max_length=300)]
    image_url: HttpUrl | None = None


class RegisterIn(BaseModel):
    name: Annotated[str, Trimmed, Field(min_length=2, max_length=100)]
    email: LowerEmail
    password: str = Field(min_length=8, max_length=72)
    phone: Annotated[str, Trimmed, Field(pattern=PHONE_PATTERN)]
    address: Annotated[str, Trimmed, Field(max_length=300)] | None = None
    role: Role
    restaurant: RestaurantIn | None = None

    @model_validator(mode="after")
    def owner_needs_restaurant(self) -> "RegisterIn":
        if self.role is Role.RESTAURANT_OWNER and self.restaurant is None:
            raise ValueError("Restaurant details are required for restaurant owners")
        return self


class LoginIn(BaseModel):
    # Deliberately not EmailStr: a malformed address is just "unknown credentials" (generic 401),
    # and login must keep working for any address that already exists in the database.
    email: Annotated[str, Trimmed, AfterValidator(_lowercase), Field(min_length=1, max_length=255)]
    password: str = Field(min_length=1, max_length=72)


class UserOut(BaseModel):
    """Public profile. Never includes ``password_hash`` (Req 4.8)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    # ``str`` rather than ``EmailStr`` so serialising an existing row can never fail validation
    # (for example a seeded address on a reserved domain such as ``.local``).
    email: str
    role: Role
    phone: str | None = None
    address: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut
