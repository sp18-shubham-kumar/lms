"""
Authorization primitives.

The spec draws a hard line between two questions:

- **Capability** — "may this person ever do X?" (e.g. ``skill.verify``). Comes
  from role grants.
- **Authority** — "may they do X to *this* resource?" (e.g. verify *this* skill
  at *this* level for *this* org subtree). Comes from ``verifier_authority``.

Everything funnels through a single entry point, ``can(actor, capability,
resource)``, deny-by-default. Phase 1 implements the capability half; the
authority half lands with the verify module.
"""

from __future__ import annotations

import logging
from typing import Any

from rest_framework.permissions import BasePermission

from core.context import get_current_tenant

logger = logging.getLogger("authz")


def _log_deny(actor: Any, capability: str, reason: str) -> None:
    logger.info(
        "authz.deny",
        extra={
            "actor": getattr(actor, "id", None),
            "capability": capability,
            "reason": reason,
        },
    )


def capabilities_for(actor: Any, tenant_id: Any) -> set[str]:
    """Resolve the capability keys an actor holds in a tenant, via role grants."""
    from apps.authz.models import RoleCapability, RoleGrant

    role_ids = list(
        RoleGrant.all_tenants.filter(
            tenant_id=tenant_id, principal_type="person", principal_id=actor.id
        ).values_list("role_id", flat=True)
    )
    if not role_ids:
        return set()
    return set(
        RoleCapability.all_tenants.filter(tenant_id=tenant_id, role_id__in=role_ids).values_list(
            "capability_id", flat=True
        )
    )


def can(actor: Any, capability: str, resource: Any | None = None) -> bool:
    """Single authorization entry point. Deny by default; log every deny."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        _log_deny(actor, capability, "unauthenticated")
        return False
    if getattr(actor, "is_superuser", False):
        return True
    tenant_id = get_current_tenant()
    if tenant_id is None:
        _log_deny(actor, capability, "no-tenant-context")
        return False
    # Per-request memo, keyed by tenant.
    cache = getattr(actor, "_cap_cache", None)
    if cache is None:
        cache = {}
        actor._cap_cache = cache
    caps = cache.get(tenant_id)
    if caps is None:
        caps = capabilities_for(actor, tenant_id)
        cache[tenant_id] = caps
    if capability in caps:
        return True
    _log_deny(actor, capability, "capability-not-held")
    return False


class HasCapability(BasePermission):
    """
    DRF permission that gates a view on a required capability.

    Set ``required_capability`` on the view::

        class SkillViewSet(viewsets.ModelViewSet):
            required_capability = "taxonomy.edit"
            permission_classes = [HasCapability]
    """

    message = "You do not have the capability required for this action."

    def has_permission(self, request: Any, view: Any) -> bool:
        capability = getattr(view, "required_capability", None)
        if capability is None:
            # Misconfiguration is a denial, not an allow.
            return False
        return can(request.user, capability)

    def has_object_permission(self, request: Any, view: Any, obj: Any) -> bool:
        capability = getattr(view, "required_capability", None)
        if capability is None:
            return False
        return can(request.user, capability, obj)
