"""Helpers for ids taken from the URL."""

INT32_MAX = 2**31 - 1  # largest value of a PostgreSQL INTEGER primary key


def fits_int32(value: int) -> bool:
    """True when ``value`` can be a row id (a positive 32-bit INTEGER).

    PostgreSQL raises "integer out of range" (an HTTP 500) when a larger value is compared with an
    INTEGER column, so a path id that cannot exist must be answered with 404 before querying.
    """
    return 0 < value <= INT32_MAX
