"""Helpers for case-insensitive substring search (Req 8.2, 9.1)."""
from sqlalchemy import ColumnElement

LIKE_ESCAPE = "\\"


def escape_like(text: str) -> str:
    """Escape ``\\``, ``%`` and ``_`` so user text is matched literally inside a LIKE pattern."""
    return (
        text.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2)
        .replace("%", LIKE_ESCAPE + "%")
        .replace("_", LIKE_ESCAPE + "_")
    )


def clean_search(text: str | None) -> str | None:
    """Trim the search text; ``None`` when blank. NUL bytes are dropped (PostgreSQL rejects them)."""
    if text is None:
        return None
    cleaned = text.replace("\x00", "").strip()
    return cleaned or None


def contains_ci(column: ColumnElement, text: str) -> ColumnElement[bool]:
    """``column ILIKE '%text%' ESCAPE '\\'`` with ``text`` matched literally."""
    return column.ilike(f"%{escape_like(text)}%", escape=LIKE_ESCAPE)
