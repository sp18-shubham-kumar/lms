"""
Skill taxonomy models (Phase 1 CRUD, Phase 2 framework).

Tables (see docs/specs/data-model.md, phase-1.md, phase-2.md):
- SkillDomain   — grouping (tenant_id NULL = global).
- Skill         — a capability; versioned, never mutated in place; retire, don't delete.
- SelfDeclaredSkill (Phase 1) — a member's self-claim (the untrusted tier).

Base-class choice for globals
------------------------------
``SkillDomain`` and ``Skill`` can be either a **global/platform row** (``tenant`` NULL,
shared across tenants, read-only to tenants) or a **tenant-owned row**. They therefore
CANNOT inherit :class:`core.models.TenantScopedModel`, whose ``tenant`` FK is NOT NULL and
whose scoped ``objects`` manager returns only strict ``tenant_id == current`` rows (globals
would be invisible).

Instead they inherit a dedicated :class:`GlobalOrTenantModel` base: UUID id + timestamps +
a *nullable* ``tenant`` FK, and a manager whose ``.visible()`` returns the union of globals
(``tenant__isnull=True``) and the current tenant's rows (fail-closed: globals only when no
tenant is in context). The default ``objects`` manager is unscoped by design (globals must
be creatable/readable in provisioning/seed); request handlers must call ``.visible()``.

``SelfDeclaredSkill`` is always tenant-owned and inherits ``TenantScopedModel`` normally.
Self-declared (Phase 1) and verified assertions (Phase 2) stay separate records.
"""

from __future__ import annotations

from django.db import models

from core.context import get_current_tenant
from core.models import TenantScopedModel, TimeStampedModel, UUIDModel


class GlobalOrTenantQuerySet(models.QuerySet):
    """QuerySet whose ``visible()`` returns globals plus the current tenant's rows."""

    def visible(self) -> GlobalOrTenantQuerySet:
        tenant_id = get_current_tenant()
        if tenant_id is None:
            # Fail closed to globals only when no tenant is in context.
            return self.filter(tenant__isnull=True)
        return self.filter(models.Q(tenant__isnull=True) | models.Q(tenant_id=tenant_id))


class GlobalOrTenantManager(models.Manager.from_queryset(GlobalOrTenantQuerySet)):  # type: ignore[misc]
    """Unscoped manager; use ``.visible()`` in request handlers (globals ∪ tenant)."""


class GlobalOrTenantModel(UUIDModel, TimeStampedModel):
    """
    Base for rows that are either global (``tenant`` NULL) or tenant-owned.

    Unlike :class:`core.models.TenantScopedModel`, the ``tenant`` FK is nullable and the
    default manager is unscoped; call ``objects.visible()`` to get globals ∪ current tenant.
    """

    tenant = models.ForeignKey(
        "identity.Tenant",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    objects = GlobalOrTenantManager()

    class Meta:
        abstract = True


class SkillDomain(GlobalOrTenantModel):
    """A grouping of skills. ``tenant`` NULL = a global/platform domain."""

    name = models.CharField(max_length=255)
    sort = models.SmallIntegerField(default=0)

    class Meta:
        ordering = ["sort", "name"]

    def __str__(self) -> str:
        return self.name


class Skill(GlobalOrTenantModel):
    """A capability. Versioned, never mutated in place; retire, never delete."""

    STATUS_CHOICES = [
        ("draft", "draft"),
        ("published", "published"),
        ("retired", "retired"),
    ]

    domain = models.ForeignKey(SkillDomain, on_delete=models.PROTECT, related_name="skills")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255)
    external_code = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    version = models.SmallIntegerField(default=1)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "slug", "version"], name="uniq_skill_tenant_slug_version"
            )
        ]

    def __str__(self) -> str:
        return self.name


class SelfDeclaredSkill(TenantScopedModel):
    """A member's self-claim (the untrusted tier, separate from verified assertions)."""

    membership = models.ForeignKey(
        "identity.Membership", on_delete=models.CASCADE, related_name="self_declared_skills"
    )
    skill = models.ForeignKey(Skill, on_delete=models.PROTECT, related_name="+")
    level = models.SmallIntegerField(null=True, blank=True)
    note = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "skill"], name="uniq_self_declared_membership_skill"
            )
        ]

    def __str__(self) -> str:
        return f"SelfDeclaredSkill({self.membership_id}, {self.skill_id})"
