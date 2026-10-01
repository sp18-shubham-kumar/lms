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

from collections.abc import Callable
from typing import Any

from django.db import IntegrityError, transaction
from rest_framework.response import Response

IDEMPOTENCY_HEADER = "HTTP_IDEMPOTENCY_KEY"


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

    existing = IdempotencyRecord.objects.filter(key=key, method=method, path=path).first()
    if existing is not None:
        return Response(existing.response_body, status=existing.response_status)

    response = response_factory()
    # Ensure DRF has rendered serializer data into a plain structure we can store.
    body = response.data if hasattr(response, "data") else None
    try:
        with transaction.atomic():
            IdempotencyRecord.objects.create(
                tenant_id=tenant_id,
                key=key,
                method=method,
                path=path,
                response_status=response.status_code,
                response_body=body if body is not None else {},
            )
    except IntegrityError:
        # A concurrent request won the unique constraint; return the stored result.
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
