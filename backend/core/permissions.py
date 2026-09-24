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

This module ships the *contract* (a base DRF permission + the ``can`` seam) so
views can be written against it now and the resolution filled in later.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission


def can(actor: Any, capability: str, resource: Any | None = None) -> bool:
    """
    Single authorization entry point. Deny by default.

    Phase 1 will resolve the actor's capability set (cached per session) and,
    where a resource is supplied, check scoped authority. Until then this returns
    ``False`` so nothing is accidentally granted.
    """
    # TODO(phase-1): resolve capabilities from role grants; add authority check.
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

    def has_permission(self, request, view) -> bool:
        capability = getattr(view, "required_capability", None)
        if capability is None:
            # Misconfiguration is a denial, not an allow.
            return False
        return can(request.user, capability)

    def has_object_permission(self, request, view, obj) -> bool:
        capability = getattr(view, "required_capability", None)
        if capability is None:
            return False
        return can(request.user, capability, obj)
