from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.skills import services
from apps.skills.models import SelfDeclaredSkill, Skill, SkillDomain
from apps.skills.serializers import (
    SelfDeclaredSkillSerializer,
    SkillDomainSerializer,
    SkillSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

READ_CAPABILITY = "directory.view"
WRITE_CAPABILITY = "taxonomy.edit"
DECLARE_CAPABILITY = "skill.claim.submit"

# Actions that mutate state require taxonomy.edit; reads require directory.view.
_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}


@extend_schema_view(
    list=extend_schema(summary="List skill domains", tags=["Skills"]),
    retrieve=extend_schema(summary="Retrieve a skill domain", tags=["Skills"]),
)
@extend_schema(tags=["Skills"])
class SkillDomainViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve skill domains visible to the tenant (globals + tenant rows)."""

    serializer_class = SkillDomainSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = READ_CAPABILITY

    def get_queryset(self) -> Any:
        # .visible() = globals (tenant NULL) ∪ current tenant rows (fail-closed).
        return SkillDomain.objects.visible().order_by("sort", "name")


@extend_schema_view(
    list=extend_schema(summary="List skills", tags=["Skills"]),
    retrieve=extend_schema(summary="Retrieve a skill", tags=["Skills"]),
    create=extend_schema(summary="Create a tenant skill", tags=["Skills"]),
    update=extend_schema(summary="Replace a skill", tags=["Skills"]),
    partial_update=extend_schema(summary="Update a skill", tags=["Skills"]),
    destroy=extend_schema(summary="Retire a skill", tags=["Skills"]),
)
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


@extend_schema_view(
    list=extend_schema(summary="List my skill declarations", tags=["Skills"]),
    create=extend_schema(summary="Declare a skill", tags=["Skills"]),
    destroy=extend_schema(summary="Remove a skill declaration", tags=["Skills"]),
)
@extend_schema(tags=["Skills"])
class SelfDeclaredSkillViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    The caller's own self-declared skills (the untrusted tier).

    Scoped to the caller's active membership in the current tenant — a member
    only ever sees/creates/deletes their *own* declarations. Audited. ``level``
    is validated 1..5 and unique per (membership, skill).
    """

    serializer_class = SelfDeclaredSkillSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = DECLARE_CAPABILITY

    def _current_membership(self) -> Any:
        from apps.identity.models import Membership

        membership = Membership.objects.filter(person=self.request.user, status="active").first()
        if membership is None:
            raise PermissionDenied("No active membership in this tenant.")
        return membership

    def get_queryset(self) -> Any:
        # Only the caller's own declarations (tenant-scoped manager + membership).
        return (
            SelfDeclaredSkill.objects.filter(membership=self._current_membership())
            .select_related("skill")
            .order_by("skill__name")
        )

    def perform_create(self, serializer: Any) -> None:
        membership = self._current_membership()
        skill = serializer.validated_data["skill"]
        tenant_id = get_current_tenant()
        if SelfDeclaredSkill.objects.filter(membership=membership, skill=skill).exists():
            raise ValidationError("You have already declared this skill.")
        declaration = serializer.save(membership=membership, tenant_id=tenant_id)
        audit.record(
            actor=self.request.user,
            action="skill.declare",
            resource=declaration,
            tenant_id=tenant_id,
            skill_id=str(skill.id),
        )

    def perform_destroy(self, instance: SelfDeclaredSkill) -> None:
        audit.record(
            actor=self.request.user,
            action="skill.declare.remove",
            resource=instance,
            tenant_id=instance.tenant_id,
            skill_id=str(instance.skill_id),
        )
        instance.delete()
