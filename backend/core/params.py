"""
Query-parameter parsing shared by the domain views.

Filtering a ``UUIDField`` on a malformed string raises Django's ``ValidationError``
deep inside the ORM, which DRF doesn't handle, so the caller gets a 500. Parse
UUID parameters up front instead and answer a malformed one with a 400.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework.exceptions import ParseError


def uuid_param(request: Any, name: str, *, required: bool = False) -> uuid.UUID | None:
    """
    The ``name`` query parameter as a UUID, or ``None`` when it is absent or blank.

    Raises :class:`ParseError` (400) when the parameter is malformed, or missing and
    ``required``.
    """
    raw = request.query_params.get(name)
    if not raw:
        if required:
            raise ParseError(f"Query parameter '{name}' is required.")
        return None
    try:
        return uuid.UUID(raw)
    except ValueError as exc:
        raise ParseError(f"Query parameter '{name}' must be a UUID.") from exc
