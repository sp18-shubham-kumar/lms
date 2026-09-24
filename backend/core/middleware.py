"""
Tenant context middleware.

Resolves the active tenant for each request and publishes it to
:mod:`core.context` so tenant-scoped managers filter correctly. The resolved
tenant is also attached to ``request.tenant_id`` for convenience.

MVP resolution order (kept simple on purpose; extend in Phase 1):
1. ``X-Tenant-Id`` header (the SPA sends this after the tenant picker).
2. Subdomain-based resolution can be layered in later without touching callers.

Once :class:`apps.identity.Tenant` and ``Membership`` exist, this middleware
should also verify the authenticated user actually belongs to the requested
tenant and reject the request otherwise. That check is intentionally left as a
TODO until the identity models land.
"""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

from core.context import reset_current_tenant, set_current_tenant


class TenantContextMiddleware(MiddlewareMixin):
    def process_request(self, request) -> None:
        raw = request.META.get(settings.TENANT_HEADER)
        tenant_id: UUID | None = None
        if raw:
            try:
                tenant_id = UUID(str(raw))
            except (ValueError, TypeError):
                tenant_id = None

        # TODO(phase-1): once Membership exists, assert request.user is a member
        # of tenant_id before trusting the header.
        request.tenant_id = tenant_id
        request._tenant_token = set_current_tenant(tenant_id)

    def process_response(self, request, response):
        token = getattr(request, "_tenant_token", None)
        if token is not None:
            reset_current_tenant(token)
        return response

    def process_exception(self, request, exception):
        token = getattr(request, "_tenant_token", None)
        if token is not None:
            reset_current_tenant(token)
        return None
