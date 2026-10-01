"""
Idempotency-Key handling for write endpoints.

Clients retry writes; the architecture rule is that a retry carrying the same
``Idempotency-Key`` header must return the original result without creating a
duplicate row. This module provides:

- :func:`idempotent` — run a response factory once per
  ``(tenant, key, method, path)``; on replay return the stored status/body.
- :class:`IdempotentCreateMixin` — a DRF viewset mixin that wraps ``create``.

Requests without the header run normally and store nothing. Scoping is per
tenant (records inherit :class:`core.models.TenantScopedModel`), so the active
tenant must be in context when these are called (request path guarantees it).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, transaction
from rest_framework.response import Response

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"


def _json_safe(body: Any) -> Any:
    """Coerce serializer output (UUIDs, datetimes, Decimals) into JSON-native types."""
    return json.loads(json.dumps(body, cls=DjangoJSONEncoder))


def _key_from(request: Any) -> str | None:
    key = request.META.get(IDEMPOTENCY_HEADER)
    return str(key) if key else None


def idempotent(
    request: Any,
    tenant_id: Any,
    response_factory: Callable[[], Response],
) -> Response:
    """
    Execute ``response_factory`` at most once per ``(tenant, key, method, path)``.

    - No ``Idempotency-Key`` header: run the factory and return it (nothing stored).
    - First call with a key: run the factory, persist status + body, return it.
    - Replay (same tenant/key/method/path): return the stored status/body.
    """
    from core.models import IdempotencyRecord

    key = _key_from(request)
    if key is None:
        return response_factory()

    method = request.method
    path = request.path

    # Use SELECT FOR UPDATE inside a transaction so that concurrent first-calls
    # with the same key queue behind one another rather than both running the
    # factory and creating the underlying resource twice.  The lock is advisory
    # (row-level on IdempotencyRecord); if no row exists yet we rely on the
    # UNIQUE constraint as the final backstop and discard the duplicate result.
    with transaction.atomic():
        try:
            existing = (
                IdempotencyRecord.objects.select_for_update()
                .filter(key=key, method=method, path=path)
                .first()
            )
        except Exception:
            # select_for_update may raise outside a transaction (e.g. in tests
            # with AUTOCOMMIT); fall back to a plain read.
            existing = IdempotencyRecord.objects.filter(key=key, method=method, path=path).first()

        if existing is not None:
            return Response(existing.response_body, status=existing.response_status)

        response = response_factory()
        # Ensure DRF has rendered serializer data into a plain structure we can store.
        raw_body = response.data if hasattr(response, "data") else None
        body = _json_safe(raw_body) if raw_body is not None else {}
        try:
            IdempotencyRecord.objects.create(
                tenant_id=tenant_id,
                key=key,
                method=method,
                path=path,
                response_status=response.status_code,
                response_body=body,
            )
        except IntegrityError:
            # Concurrent request won despite the lock (e.g. different DB session).
            record = IdempotencyRecord.objects.get(key=key, method=method, path=path)
            return Response(record.response_body, status=record.response_status)
    return response


class IdempotentCreateMixin:
    """
    Mixin for DRF viewsets: wrap a create in :func:`idempotent`.

    Call :meth:`idempotent_create` from ``create`` with a callable that performs
    the real create and returns a DRF ``Response``.
    """

    def idempotent_create(self, request: Any, response_factory: Callable[[], Response]) -> Response:
        from core.context import get_current_tenant

        tenant_id = getattr(request, "tenant_id", None) or get_current_tenant()
        return idempotent(request, tenant_id, response_factory)
