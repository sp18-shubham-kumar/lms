"""
Tenant context middleware.

Resolves the active tenant for each request and publishes it to
:mod:`core.context` so tenant-scoped managers filter correctly. The resolved
tenant is also attached to ``request.tenant_id`` for convenience.

Resolution order (kept simple on purpose):
1. ``X-Tenant-Id`` header (the SPA sends this after the tenant picker).
2. Subdomain-based resolution can be layered in later without touching callers.

Membership enforcement
-----------------------
When a request carries a tenant header *and* the caller is authenticated, the
middleware asserts the caller has an ``active`` :class:`identity.Membership` in
that tenant, rejecting (403 JSON) before any view runs. Authentication happens
at the DRF layer (JWT), which runs *after* middleware, so we authenticate the
request here with the configured DRF authenticators to resolve the user.

Unauthenticated / public endpoints (health, login, schema) carry no tenant/user
requirement: with no credentials the membership check is skipped and the view's
own permissions decide the outcome. ``IsActiveTenantMember`` at the DRF layer
remains the belt-and-braces check.
"""

from __future__ import annotations

from uuid import UUID

from django.conf import settings
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

from core.context import reset_current_tenant, set_current_tenant


def _authenticated_person(request):
    """Resolve the request's authenticated person, or ``None``.

    Django's ``AuthenticationMiddleware`` only handles session auth; this API is
    JWT-only (resolved by DRF after middleware). We run the configured DRF
    authenticators here so the membership check sees the real caller. A missing
    or invalid token simply yields ``None`` (treated as unauthenticated).
    """
    from rest_framework.exceptions import APIException
    from rest_framework.request import Request
    from rest_framework.views import APIView

    drf_request = Request(request, authenticators=APIView().get_authenticators())
    try:
        return drf_request.user if drf_request.successful_authenticator else None
    except APIException:
        return None


class TenantContextMiddleware(MiddlewareMixin):
    def process_request(self, request) -> JsonResponse | None:
        raw = request.META.get(settings.TENANT_HEADER)
        tenant_id: UUID | None = None
        if raw:
            try:
                tenant_id = UUID(str(raw))
            except (ValueError, TypeError):
                tenant_id = None

        # Enforce membership at the boundary: only when a tenant header resolved
        # AND the request is authenticated. Public/unauthenticated endpoints pass
        # through untouched.
        if tenant_id is not None:
            person = _authenticated_person(request)
            if person is not None and getattr(person, "is_authenticated", False):
                from apps.identity.models import Membership

                is_member = Membership.all_tenants.filter(
                    person=person, tenant_id=tenant_id, status="active"
                ).exists()
                if not is_member:
                    return JsonResponse({"detail": "Not a member of this tenant."}, status=403)

        request.tenant_id = tenant_id
        request._tenant_token = set_current_tenant(tenant_id)
        return None

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
