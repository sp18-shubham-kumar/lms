"""
Cross-tenant isolation scan command.

Discovers every concrete TenantScopedModel subclass and, for each distinct
tenant_id present in that table, sets the ambient tenant context and queries
Model.objects.all() (which is tenant-scoped). If any returned row has a
tenant_id that does not match the context tenant, it is a manager bug (a leak).

In practice, if TenantScopedManager is correctly implemented, this can never
find a leak — the scan proves the invariant holds. If someone patches the
manager or forgets to scope a queryset, the scan catches it.

Exit codes:
    0 — no leaks found (all tables, all tenants, clean)
    1 — at least one leak detected (report printed to stdout)

Usage:
    python manage.py scan_isolation
"""

from __future__ import annotations

import sys
from typing import Any
from uuid import UUID

from django.apps import apps
from django.core.management.base import BaseCommand

from core.context import tenant_context
from core.models import TenantScopedModel


class Command(BaseCommand):
    help = "Scan all TenantScopedModel subclasses for cross-tenant data leaks."

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Iterate every concrete TenantScopedModel subclass; for each distinct
        tenant_id, enter that tenant's context and assert objects.all() returns
        only that tenant's rows.
        """
        leak_messages: list[str] = []

        tenant_scoped_models = self._discover_models()
        if not tenant_scoped_models:
            self.stdout.write("No TenantScopedModel subclasses found. OK\n")
            return

        for model_class in tenant_scoped_models:
            # Discover all distinct tenant_ids present in this table.
            # Use all_tenants (escape hatch) to enumerate all rows across tenants.
            tenant_ids: list[UUID] = list(
                model_class.all_tenants.values_list("tenant_id", flat=True).distinct()
            )
            for tenant_id in tenant_ids:
                leaks = self.check_model_for_leak(model_class, tenant_id)
                leak_messages.extend(leaks)

        if leak_messages:
            self.stdout.write("=== ISOLATION SCAN: LEAKS FOUND ===\n")
            for msg in leak_messages:
                self.stdout.write(f"  {msg}\n")
            self.stdout.write(f"Total leaks: {len(leak_messages)}\n")
            sys.exit(1)
        else:
            model_names = ", ".join(m.__name__ for m in tenant_scoped_models)
            self.stdout.write(
                f"=== ISOLATION SCAN: PASS ===\n"
                f"Checked models: {model_names}\n"
                f"No leaks detected. All tenant scoping is clean.\n"
            )

    def check_model_for_leak(
        self, model_class: type[TenantScopedModel], tenant_id: UUID
    ) -> list[str]:
        """
        Under tenant_id's context, use Model.objects.all() (tenant-scoped) and
        verify every returned row actually belongs to tenant_id.

        Returns a list of leak description strings (empty if clean).
        """
        leaks: list[str] = []
        with tenant_context(tenant_id):
            # The scoped manager should only return rows for this tenant.
            cross_tenant_rows = (
                model_class.objects.all()
                .exclude(tenant_id=tenant_id)
                .values_list("id", "tenant_id")[:10]  # cap at 10 per check
            )
            for row_id, row_tenant_id in cross_tenant_rows:
                leaks.append(
                    f"{model_class.__name__}: row {row_id} has tenant_id={row_tenant_id} "
                    f"but was visible under context tenant_id={tenant_id}"
                )
        return leaks

    @staticmethod
    def _discover_models() -> list[type[TenantScopedModel]]:
        """
        Return all concrete (non-abstract) TenantScopedModel subclasses discovered
        via the Django app registry.
        """
        result: list[type[TenantScopedModel]] = []
        for model in apps.get_models():
            if model._meta.abstract:
                continue
            # Check if TenantScopedModel is in the model's MRO.
            if not issubclass(model, TenantScopedModel):
                continue
            # Verify it has a tenant field (belt-and-suspenders).
            if not hasattr(model, "tenant"):
                continue  # pragma: no cover
            result.append(model)
        return result
