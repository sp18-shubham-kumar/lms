"""
Authorization models (Phase 1).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-1.md):
- Capability        — flat, seeded key list (not tenant-editable).
- Role / RoleCapability — named bundles of capabilities per tenant.
- RoleGrant         — grants a role to a principal (person|group) within a scope.
- VerifierAuthority — who may verify which skill, up to which level, for which
                      org subtree, within a validity window (Phase 2+ usage).

All rows except `Capability` inherit `core.models.TenantScopedModel`.
Authorization decisions funnel through `core.permissions.can()`.
"""

from __future__ import annotations

from django.db import models

from core.models import TenantScopedModel


class Capability(models.Model):
    """Flat, seeded capability key. Global (not tenant-editable, not tenant-scoped)."""

    key = models.CharField(max_length=100, primary_key=True)

    def __str__(self) -> str:
        return self.key


class Role(TenantScopedModel):
    name = models.CharField(max_length=100)
    is_system = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name


class RoleCapability(TenantScopedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="capabilities")
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["role", "capability"], name="uniq_role_capability")
        ]


class RoleGrant(TenantScopedModel):
    principal_type = models.CharField(max_length=16, default="person")  # person | group
    principal_id = models.UUIDField()
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="grants")
    scope_type = models.CharField(max_length=32, blank=True, default="")
    scope_id = models.UUIDField(null=True, blank=True)
