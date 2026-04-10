"""Unique ID generation using ULID for chronological sortability."""

from ulid import ULID


def new_id() -> str:
    """Return a new unique ULID string."""
    return str(ULID())
