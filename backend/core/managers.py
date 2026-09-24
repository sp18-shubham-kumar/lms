"""
Tenant-scoped manager and queryset.

Any model that inherits :class:`core.models.TenantScopedModel` gets a default
manager that automatically filters to the tenant in :mod:`core.context`. This is
the application-layer half of tenant isolation (the plan's "shared schema +
tenant_id" decision).

Rules
-----
- ``Model.objects`` is tenant-scoped: it returns only rows for the current
  tenant. If no tenant is in context it returns **nothing** (fail closed).
- ``Model.all_tenants`` is an escape hatch for provisioning, admin, and the
  nightly cross-tenant isolation scan. Use it deliberately and never in a
  request handler.
"""

from __future__ import annotations

from django.db import models

from core.context import get_current_tenant


class TenantScopedQuerySet(models.QuerySet):
    """QuerySet that can restrict itself to the active tenant."""

    def for_current_tenant(self) -> TenantScopedQuerySet:
        tenant_id = get_current_tenant()
        if tenant_id is None:
            # Fail closed: no tenant context means no rows.
            return self.none()
        return self.filter(tenant_id=tenant_id)


class TenantScopedManager(models.Manager.from_queryset(TenantScopedQuerySet)):  # type: ignore[misc]
    """Default manager that scopes every query to the current tenant."""

    def get_queryset(self) -> TenantScopedQuerySet:
        return super().get_queryset().for_current_tenant()
