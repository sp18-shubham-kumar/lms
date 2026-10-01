from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.skills import services
from apps.skills.models import Skill, SkillDomain
from apps.skills.serializers import SkillDomainSerializer, SkillSerializer
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

READ_CAPABILITY = "directory.view"
WRITE_CAPABILITY = "taxonomy.edit"

# Actions that mutate state require taxonomy.edit; reads require directory.view.
_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}


@extend_schema(tags=["Skills"])
class SkillDomainViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve skill domains visible to the tenant (globals + tenant rows)."""

    serializer_class = SkillDomainSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = READ_CAPABILITY

    def get_queryset(self) -> Any:
        # .visible() = globals (tenant NULL) ∪ current tenant rows (fail-closed).
        return SkillDomain.objects.visible().order_by("sort", "name")


@extend_schema(tags=["Skills"])
class SkillViewSet(IdempotentCreateMixin, viewsets.ModelViewSet):
    """
    CRUD for skills. Reads (``directory.view``) return globals + tenant rows.

    Writes (``taxonomy.edit``) create/edit the current tenant's own skills only;
    global skills (``tenant`` NULL) are read-only to tenants. DELETE retires
    (``status="retired"``) rather than deleting — assertions point at the row.
    Create is idempotent via the ``Idempotency-Key`` header; writes are audited.
    """

    serializer_class = SkillSerializer
    required_capability = WRITE_CAPABILITY

    def get_permissions(self) -> list[Any]:
        capability = WRITE_CAPABILITY if self.action in _WRITE_ACTIONS else READ_CAPABILITY
        self.required_capability = capability
        perms: list[Any] = [perm() for perm in APIView.permission_classes]
        perms.append(HasCapability())
        return perms

    def get_queryset(self) -> Any:
        return Skill.objects.visible().select_related("domain").order_by("name")

    def _reject_global(self, instance: Skill) -> None:
        if instance.tenant_id is None:
            raise PermissionDenied("Global skills are read-only to tenants.")

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(request, lambda: super(SkillViewSet, self).create(request))

    def perform_create(self, serializer: Any) -> None:
        tenant_id = get_current_tenant()
        skill = serializer.save(tenant_id=tenant_id, status="draft", version=1)
        audit.record(
            actor=self.request.user,
            action="skill.create",
            resource=skill,
            tenant_id=tenant_id,
            skill_id=str(skill.id),
        )

    def perform_update(self, serializer: Any) -> None:
        self._reject_global(serializer.instance)
        skill = serializer.save()
        audit.record(
            actor=self.request.user,
            action="skill.update",
            resource=skill,
            tenant_id=skill.tenant_id,
            skill_id=str(skill.id),
        )

    def perform_destroy(self, instance: Skill) -> None:
        # DELETE == retire (never delete; assertions point at it).
        self._reject_global(instance)
        services.retire_skill(instance, self.request.user)
