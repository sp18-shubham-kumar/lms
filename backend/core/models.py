"""
Abstract base models shared across every domain app.

Inherit these instead of ``django.db.models.Model`` so tenancy, UUID keys, and
timestamps stay consistent. See backend/CLAUDE.md for the "how to add a model"
checklist.
"""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from core.managers import TenantScopedManager


class UUIDModel(models.Model):
    """Primary key is a UUID (avoids leaking row counts, safe across shards)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class TimeStampedModel(models.Model):
    """Adds created/updated audit timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantScopedModel(UUIDModel, TimeStampedModel):
    """
    Base for every tenant-owned table.

    - Carries a ``tenant`` FK (the plan's rule: *every* domain row has tenant_id).
    - ``objects`` is tenant-scoped (see :class:`core.managers.TenantScopedManager`).
    - ``all_tenants`` bypasses scoping for provisioning / admin / isolation scans.

    The FK target is referenced lazily as ``identity.Tenant`` so this base can be
    imported before the identity app defines the concrete model (Phase 1).
    """

    tenant = models.ForeignKey(
        "identity.Tenant",
        on_delete=models.CASCADE,
        related_name="+",
        db_index=True,
    )

    # DJ012 false positive: the tenant field is declared before these managers.
    objects = TenantScopedManager()
    all_tenants = models.Manager()  # noqa: DJ012

    class Meta:
        abstract = True


class IdempotencyRecord(TenantScopedModel):
    """
    Remembers the first response for a client-supplied ``Idempotency-Key`` so a
    retried write returns the original result instead of creating a duplicate.

    Scoped per tenant (inherits ``tenant`` FK). Uniqueness is per
    ``(tenant, key, method, path)`` so the same key can be safely reused across
    distinct endpoints.
    """

    key = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=512)
    response_status = models.PositiveSmallIntegerField()
    response_body = models.JSONField(default=dict, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "key", "method", "path"],
                name="uniq_idempotency_tenant_key_method_path",
            )
        ]

    def __str__(self) -> str:
        return f"IdempotencyRecord({self.method} {self.path} {self.key})"


class AuditLog(UUIDModel, TimeStampedModel):
    """Append-only audit trail. NOT tenant-scoped — records cross-context events."""

    tenant = models.ForeignKey(
        "identity.Tenant",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100, blank=True, default="")
    resource_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"AuditLog({self.action})"
