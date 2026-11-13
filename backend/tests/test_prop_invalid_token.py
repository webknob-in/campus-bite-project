"""Property test for invalid token rejection (Requirements 6.1, 6.6).

``GET /auth/me`` is the only route behind ``get_current_user`` today, and every protected route
(including the role-restricted ones built with ``require_roles``) goes through that same
dependency, so it is the probe for "every protected endpoint". A single customer exists in the
database; each generated credential is something other than a JWT signed with ``JWT_SECRET`` that
is current and well-formed, and the response must always be the same 401.
"""

from __future__ import annotations

import base64
import json
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Role, User
from tests.conftest import TEST_JWT_SECRET, make_token
from tests.factories import make_customer

# Signing an HS384/HS512 token with the 44-byte test secret is deliberate (a wrong-algorithm
# token); PyJWT only warns that the key is short for those hashes.
pytestmark = pytest.mark.filterwarnings("ignore::jwt.warnings.InsecureKeyLengthWarning")

PROTECTED_PATH = "/auth/me"
CLAIMS = ("sub", "role", "exp")

PBT_SETTINGS = settings(
    max_examples=300,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

# --------------------------------------------------------------------------------------------
# Token construction helpers
# --------------------------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(segment: str) -> bytes:
    return base64.urlsafe_b64decode(segment + "=" * (-len(segment) % 4))


def _claims(user: User, **overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "sub": str(user.id),
        "role": user.role.value,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=60),
    }
    claims.update(overrides)
    return claims


def _encode(claims: dict[str, Any], secret: str = TEST_JWT_SECRET, alg: str = "HS256") -> str:
    return jwt.encode(claims, secret, algorithm=alg)


def _raw_token(header: dict[str, Any], claims: dict[str, Any], signature: bytes) -> str:
    """Assemble a token by hand so the header can claim an algorithm PyJWT would not sign with."""
    payload = {k: (int(v.timestamp()) if isinstance(v, datetime) else v) for k, v in claims.items()}
    head = _b64(json.dumps(header, separators=(",", ":")).encode())
    body = _b64(json.dumps(payload, separators=(",", ":")).encode())
    return f"{head}.{body}.{_b64(signature)}"


def _flip(data: bytes, seed: int, mask: int) -> bytes:
    """Return ``data`` with one byte XORed by a non-zero mask, so the bytes always change."""
    buf = bytearray(data)
    buf[seed % len(buf)] ^= mask
    return bytes(buf)


# --------------------------------------------------------------------------------------------
# Strategies: each draws a "recipe" (a plain tuple), built into an Authorization header below
# --------------------------------------------------------------------------------------------

printable = st.characters(min_codepoint=0x20, max_codepoint=0x7E)
visible = st.characters(min_codepoint=0x21, max_codepoint=0x7E)
b64_text = st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_", max_size=60)

garbage_strings = st.one_of(
    st.text(alphabet=printable, max_size=300),
    st.lists(b64_text, min_size=1, max_size=4).map(".".join),  # JWT-shaped but meaningless
)

wrong_schemes = st.one_of(
    st.sampled_from(["Basic", "Token", "Digest", "JWT", "Negotiate", "Bearer:"]),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-", min_size=1, max_size=12).filter(
        lambda s: s.lower() != "bearer"
    ),
)

foreign_secrets = st.text(alphabet=visible, min_size=64, max_size=80).filter(lambda s: s != TEST_JWT_SECRET)


def _is_int_like(value: str) -> bool:
    try:
        int(value)
    except ValueError:
        return False
    return True


non_integer_subs: st.SearchStrategy[Any] = st.one_of(
    st.text(max_size=20).filter(lambda s: not _is_int_like(s)),
    st.sampled_from(["abc", "", " ", "1.5", "0x10", "1e3", "NaN", "None", "null", "٣x", "7;DROP TABLE users"]),
    st.none(),
    st.booleans(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.integers(),  # a JSON number instead of a string
    st.lists(st.integers(), max_size=3),
    st.dictionaries(st.text(max_size=5), st.integers(), max_size=2),
)

recipes = st.one_of(
    st.tuples(st.just("missing_header")),
    st.tuples(st.just("bare_bearer"), st.sampled_from(["Bearer", "Bearer ", "bearer", "BEARER  "])),
    st.tuples(st.just("wrong_scheme"), wrong_schemes, st.booleans(), garbage_strings),
    st.tuples(st.just("garbage"), garbage_strings),
    st.tuples(st.just("foreign_secret"), foreign_secrets, st.sampled_from(["HS256", "HS384", "HS512"])),
    st.tuples(st.just("wrong_alg_right_secret"), st.sampled_from(["HS384", "HS512"])),
    st.tuples(
        st.just("unsigned_or_asymmetric"),
        st.sampled_from(["none", "None", "NONE", "RS256", "ES256", "HS256"]),
        st.binary(max_size=64),
    ),
    st.tuples(st.just("expired"), st.integers(min_value=5, max_value=10**9)),
    st.tuples(st.just("missing_claims"), st.sets(st.sampled_from(CLAIMS), min_size=1).map(sorted).map(tuple)),
    st.tuples(st.just("non_integer_sub"), non_integer_subs),
    st.tuples(st.just("unknown_user"), st.integers(min_value=-(10**30), max_value=10**30).filter(bool)),
    st.tuples(
        st.just("tampered"),
        st.sampled_from(["header", "payload", "signature"]),
        st.integers(min_value=0, max_value=10**6),
        st.integers(min_value=1, max_value=255),
    ),
    st.tuples(
        st.just("swapped_claims"),
        st.sampled_from([Role.RESTAURANT_OWNER.value, Role.DELIVERY_PARTNER.value, "ADMIN", "customer"]),
        st.integers(min_value=1, max_value=10**6),
    ),
    st.tuples(st.just("truncated"), st.integers(min_value=0, max_value=10**6)),
    st.tuples(st.just("extra_segment"), b64_text),
)


def build_headers(recipe: tuple[Any, ...], user: User) -> dict[str, str]:
    """Turn a recipe into request headers. Never returns a header carrying a valid token."""
    kind, *args = recipe
    valid = make_token(user.id, user.role)

    if kind == "missing_header":
        return {}
    if kind == "bare_bearer":
        return {"Authorization": args[0]}
    if kind == "wrong_scheme":
        scheme, use_valid_token, garbage = args
        return {"Authorization": f"{scheme} {valid if use_valid_token else garbage}"}
    if kind == "garbage":
        token = args[0]
    elif kind == "foreign_secret":
        secret, alg = args
        token = _encode(_claims(user), secret, alg)
    elif kind == "wrong_alg_right_secret":
        token = _encode(_claims(user), TEST_JWT_SECRET, args[0])
    elif kind == "unsigned_or_asymmetric":
        alg, signature = args
        if alg == "HS256":
            # Header says HS256 but the signature is arbitrary bytes (a different 32-byte value).
            signature = signature if signature != _unb64(valid.split(".")[2]) else b"x"
        token = _raw_token({"alg": alg, "typ": "JWT"}, _claims(user), signature)
    elif kind == "expired":
        token = make_token(user.id, user.role, expires_in=timedelta(seconds=-args[0]))
    elif kind == "missing_claims":
        claims = _claims(user)
        for name in args[0]:
            del claims[name]
        token = _encode(claims)
    elif kind == "non_integer_sub":
        token = _encode(_claims(user, sub=args[0]))
    elif kind == "unknown_user":
        token = _encode(_claims(user, sub=str(user.id + args[0])))
    elif kind in ("tampered", "swapped_claims"):
        head, body, sig = valid.split(".")
        if kind == "swapped_claims":
            role, offset = args
            claims = json.loads(_unb64(body))
            claims["role"] = role
            claims["sub"] = str(user.id + offset)
            body = _b64(json.dumps(claims, separators=(",", ":")).encode())
        else:
            target, seed, mask = args
            if target == "header":
                head = _b64(_flip(_unb64(head), seed, mask))
            elif target == "payload":
                body = _b64(_flip(_unb64(body), seed, mask))
            else:
                sig = _b64(_flip(_unb64(sig), seed, mask))
        token = f"{head}.{body}.{sig}"
    elif kind == "truncated":
        token = valid[: args[0] % (len(valid) - 1)]
    elif kind == "extra_segment":
        token = f"{valid}.{args[0]}"
    else:  # pragma: no cover - guards against a typo in a recipe name
        raise AssertionError(f"unknown recipe kind {kind!r}")
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------------


@pytest.fixture
def customer(db: Session) -> User:
    user = make_customer(db)
    # Each 401 propagates through the ``get_db`` override, which rolls the session back. Commit
    # (releases the savepoint) so that rollback cannot discard the user between examples.
    db.commit()
    return user


def _user_count(db: Session) -> int:
    return db.scalar(select(func.count(User.id)))


@given(recipe=recipes)
@PBT_SETTINGS
def test_invalid_credentials_are_rejected_with_401(client: TestClient, db: Session, customer: User, recipe) -> None:
    """Feature: campusbite-platform, Property 5: Invalid tokens rejected

    **Validates: Requirements 6.1, 6.6**

    Whatever is sent instead of a valid, current JWT signed with ``JWT_SECRET`` (no header, wrong
    scheme, random strings, foreign secret, ``alg: none``/HS512, expired, missing or malformed
    claims, unknown user, tampered or truncated token), the protected endpoint answers 401 with a
    ``{"detail": ...}`` body and ``WWW-Authenticate: Bearer``, and exposes nothing about any user.
    """
    users_before = _user_count(db)

    response = client.get(PROTECTED_PATH, headers=build_headers(recipe, customer))

    assert response.status_code == 401, (recipe, response.status_code, response.text)
    assert response.headers["www-authenticate"] == "Bearer"
    body = response.json()
    assert set(body) == {"detail"}
    assert isinstance(body["detail"], str) and body["detail"]
    assert customer.email not in response.text
    assert customer.password_hash not in response.text
    assert _user_count(db) == users_before


@given(recipe=recipes)
@settings(PBT_SETTINGS, max_examples=100)
def test_valid_token_still_accepted_alongside_invalid_ones(
    client: TestClient, customer: User, auth_headers, recipe
) -> None:
    """Feature: campusbite-platform, Property 5: Invalid tokens rejected

    **Validates: Requirements 6.1, 6.6**

    Control: after any rejected request, a valid token for the same user still returns 200 with
    that user's profile, so the 401s above come from the credential and not from a broken route.
    """
    assert client.get(PROTECTED_PATH, headers=build_headers(recipe, customer)).status_code == 401

    response = client.get(PROTECTED_PATH, headers=auth_headers(customer))

    assert response.status_code == 200
    assert response.json()["id"] == customer.id
    assert response.json()["email"] == customer.email
