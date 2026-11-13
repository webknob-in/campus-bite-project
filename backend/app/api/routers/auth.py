"""``/auth``: register, login and the current profile (Req 4, 5, 40.1)."""

from functools import lru_cache

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.config import get_settings
from app.core.errors import ConflictError, UnauthorizedError
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Restaurant, Role, User
from app.schemas.auth import LoginIn, RegisterIn, TokenOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

INVALID_CREDENTIALS = "Invalid email or password"


@lru_cache
def _dummy_hash() -> str:
    """A valid bcrypt hash used to spend the same time on unknown emails as on known ones."""
    return hash_password("campusbite-dummy-password")


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    responses={409: {"description": "A user with this email already exists."}},
)
def register(payload: RegisterIn, db: Session = Depends(get_db)) -> User:
    """Create a User; a RESTAURANT_OWNER also gets their Restaurant in the same transaction.

    ``restaurant`` is only used for the RESTAURANT_OWNER role and ignored for other roles.
    """
    user = User(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        phone=payload.phone,
        address=payload.address,
    )
    try:
        # The savepoint keeps the session usable if the insert fails; flush surfaces the unique
        # violation here, before ``get_db`` commits, so it becomes a 409 instead of a 500.
        with db.begin_nested():
            db.add(user)
            db.flush()
            if payload.role is Role.RESTAURANT_OWNER and payload.restaurant is not None:
                data = payload.restaurant
                db.add(
                    Restaurant(
                        owner_id=user.id,
                        name=data.name,
                        description=data.description,
                        cuisine=data.cuisine,
                        address=data.address,
                        image_url=str(data.image_url) if data.image_url else None,
                    )
                )
                db.flush()
    except IntegrityError:
        raise ConflictError("A user with this email already exists") from None
    return user


@router.post(
    "/login",
    response_model=TokenOut,
    summary="Log in",
    responses={401: {"description": "Invalid email or password."}},
)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    """Return a JWT and the profile. Unknown email and wrong password give the same 401."""
    user = db.scalar(select(User).where(User.email == payload.email))
    password_ok = verify_password(payload.password, user.password_hash if user else _dummy_hash())
    if user is None or not password_ok:
        raise UnauthorizedError(INVALID_CREDENTIALS)
    token = create_access_token(user.id, user.role, get_settings())
    return TokenOut(access_token=token, token_type="bearer", user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut, summary="Current user's profile")
def me(user: User = Depends(get_current_user)) -> User:
    return user
