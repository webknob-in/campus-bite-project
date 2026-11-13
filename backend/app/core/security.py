"""Password hashing (bcrypt) and JWT helpers (PyJWT, HS256).

Token claims: ``sub`` (user id as a string), ``role`` and ``exp`` (Req 5.1, 6.6).
The signing secret and the token lifetime come from ``Settings`` (``JWT_SECRET``,
``JWT_EXPIRE_MINUTES``).

``decode_access_token`` raises a ``jwt.PyJWTError`` subclass for any bad, tampered,
foreign-secret, or expired token. The ``get_current_user`` dependency catches that and
raises ``UnauthorizedError("Invalid or expired token")``, which the error handler turns
into HTTP 401 with ``WWW-Authenticate: Bearer`` (Req 6.1).
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import Settings

JWT_ALGORITHM = "HS256"
REQUIRED_CLAIMS = ["sub", "role", "exp"]

# bcrypt only uses the first 72 bytes of the input, and bcrypt >= 5 raises ValueError for
# longer input. Request schemas cap passwords at 72 *characters*, which can still exceed
# 72 bytes in UTF-8, so both functions cut to 72 bytes. This keeps hashing and verifying
# consistent (the documented bcrypt truncation) instead of failing with a 500.
BCRYPT_MAX_BYTES = 72


def _password_bytes(raw: str) -> bytes:
    return raw.encode("utf-8")[:BCRYPT_MAX_BYTES]


def hash_password(raw: str) -> str:
    """Return a salted bcrypt hash of ``raw`` as a ``str``."""
    return bcrypt.hashpw(_password_bytes(raw), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    """Return True if ``raw`` matches the bcrypt hash ``hashed``.

    A malformed stored hash counts as a mismatch instead of raising, so a login attempt
    against a corrupt row ends in the same generic 401 as a wrong password.
    """
    try:
        return bcrypt.checkpw(_password_bytes(raw), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, role: str, s: Settings) -> str:
    """Sign a JWT with ``sub`` = user id, ``role`` and ``exp`` = now + ``jwt_expire_minutes``."""
    exp = datetime.now(timezone.utc) + timedelta(minutes=s.jwt_expire_minutes)
    claims = {
        "sub": str(user_id),
        # ``role`` may be a ``Role`` str-enum; store its plain value.
        "role": str(getattr(role, "value", role)),
        "exp": exp,
    }
    return jwt.encode(claims, s.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str, s: Settings) -> dict[str, Any]:
    """Verify signature and expiry and return the claims.

    Only HS256 is accepted (no ``alg: none`` or algorithm switching), and ``sub``,
    ``role`` and ``exp`` must all be present. Raises ``jwt.PyJWTError`` otherwise
    (``ExpiredSignatureError``, ``InvalidSignatureError``, ``DecodeError``,
    ``MissingRequiredClaimError``, ...).
    """
    return jwt.decode(
        token,
        s.jwt_secret,
        algorithms=[JWT_ALGORITHM],
        options={"require": REQUIRED_CLAIMS},
    )
