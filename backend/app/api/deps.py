from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.session import SessionLocal


def get_db() -> Iterator[Session]:
    """Yield one Session per request inside a single transaction.

    Commits when the request handler finishes without raising, and rolls back on any
    exception so a failed request never leaves partial writes (Req 47.4). Services that
    must turn a constraint violation into a 409 should ``flush()`` inside their own
    ``try``/``except IntegrityError`` so the error surfaces before this commit.
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
