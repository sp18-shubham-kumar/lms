"""Django admin helpers.

Request handlers keep using ``Model.objects`` (tenant-scoped, fail closed).
Support screens that must see every tenant use :class:`AllTenantsModelAdmin`.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.db.models import Model, QuerySet
from django.http import HttpRequest


class AllTenantsModelAdmin(admin.ModelAdmin):
    """List and edit rows from every tenant via ``all_tenants``.

    The default manager stays tenant-scoped. Only this admin queryset, and the
    foreign-key choices on its forms, bypass it.
    """

    def get_queryset(self, request: HttpRequest) -> QuerySet[Model]:
        qs: QuerySet[Model] = self.model.all_tenants.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_field_queryset(
        self, db: str | None, db_field: Any, request: HttpRequest
    ) -> QuerySet[Model] | None:
        related = db_field.remote_field.model
        manager = getattr(related, "all_tenants", None)
        if manager is None:
            return super().get_field_queryset(db, db_field, request)
        return manager.using(db).all() if db else manager.all()
