from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.skills import services
from apps.skills.models import (
    SelfDeclaredSkill,
    Skill,
    SkillAssertion,
    SkillDomain,
    SkillEdge,
    SkillLevel,
    TenantSkillOverride,
)
from apps.skills.serializers import (
    SelfDeclaredSkillSerializer,
    SkillAssertionSerializer,
    SkillDomainSerializer,
    SkillEdgeSerializer,
    SkillLevelSerializer,
    SkillLevelsReplaceSerializer,
    SkillSerializer,
    TenantSkillOverrideSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

READ_CAPABILITY = "directory.view"
WRITE_CAPABILITY = "taxonomy.edit"
DECLARE_CAPABILITY = "skill.claim.submit"
VERIFY_CAPABILITY = "skill.verify"

# Actions that mutate state require taxonomy.edit; reads require directory.view.
_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy", "edges", "override", "publish"}
# The levels action gates per-method: GET reads (directory.view), PUT writes (taxonomy.edit).


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
        method = self.request.method if self.request is not None else "GET"
        if self.action in {"levels", "edges"}:
            # Read on GET, write on PUT/POST/DELETE.
            capability = (
                READ_CAPABILITY if method in ("GET", "HEAD", "OPTIONS") else WRITE_CAPABILITY
            )
        else:
            capability = WRITE_CAPABILITY if self.action in _WRITE_ACTIONS else READ_CAPABILITY
        self.required_capability = capability
        perms: list[Any] = [perm() for perm in APIView.permission_classes]
        perms.append(HasCapability())
        return perms

    def get_queryset(self) -> Any:
        return Skill.objects.visible().select_related("domain").order_by("name")

    def list(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        # Apply tenant copy-on-write overrides (rename/hide) at read time.
        resolved = services.resolve_skill_view(self.get_queryset(), get_current_tenant())
        page = self.paginate_queryset(resolved)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(resolved, many=True)
        return Response(serializer.data)

    def retrieve(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        overrides = services._overrides_for(get_current_tenant(), [instance.id])
        override = overrides.get(instance.id)
        if override is not None and override.hidden:
            from django.http import Http404

            raise Http404
        instance = services.apply_override(instance, override)
        return Response(self.get_serializer(instance).data)

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

    @extend_schema(
        summary="Get or replace a skill's rubric grid",
        description=(
            "GET returns the skill's level rubric (1..5). PUT replaces the full grid "
            "with the posted levels (wholesale replace). Requires taxonomy.edit for PUT."
        ),
        request=SkillLevelsReplaceSerializer,
        responses=SkillLevelSerializer(many=True),
        tags=["Skills"],
    )
    @action(detail=True, methods=["get", "put"])
    def levels(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        if request.method == "GET":
            qs = SkillLevel.objects.filter(skill=skill).order_by("level")
            return Response({"levels": SkillLevelSerializer(qs, many=True).data})

        serializer = SkillLevelsReplaceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        levels_data = serializer.validated_data["levels"]
        # Replace the whole rubric grid.
        SkillLevel.objects.filter(skill=skill).delete()
        created = [SkillLevel.objects.create(skill=skill, **row) for row in levels_data]
        audit.record(
            actor=request.user,
            action="skill.levels.replace",
            resource=skill,
            tenant_id=get_current_tenant(),
            skill_id=str(skill.id),
            count=len(created),
        )
        return Response({"levels": SkillLevelSerializer(created, many=True).data})

    @extend_schema(
        summary="List, add, or delete a skill's edges",
        description=(
            "GET lists the skill's outgoing prerequisite/adjacent edges. POST adds an "
            "edge (rejecting self-edges and prerequisite cycles with 400). "
            "DELETE ?edge=<id> removes one. POST/DELETE require taxonomy.edit."
        ),
        request=SkillEdgeSerializer,
        responses=SkillEdgeSerializer,
        tags=["Skills"],
    )
    @action(detail=True, methods=["get", "post", "delete"])
    def edges(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        if request.method == "GET":
            qs = SkillEdge.objects.filter(from_skill=skill)
            return Response({"edges": SkillEdgeSerializer(qs, many=True).data})

        if request.method == "DELETE":
            edge_id = request.query_params.get("edge")
            edge = SkillEdge.objects.filter(id=edge_id, from_skill=skill).first()
            if edge is None:
                from django.http import Http404

                raise Http404
            audit.record(
                actor=request.user,
                action="skill.edge.remove",
                resource=skill,
                tenant_id=get_current_tenant(),
                skill_id=str(skill.id),
                edge_id=str(edge.id),
            )
            edge.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = SkillEdgeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_skill = serializer.validated_data["to_skill"]
        kind = serializer.validated_data["kind"]
        try:
            edge = services.add_edge(skill, to_skill, kind)
        except DjangoValidationError as exc:
            raise ValidationError(exc.messages) from exc
        audit.record(
            actor=request.user,
            action="skill.edge.add",
            resource=skill,
            tenant_id=get_current_tenant(),
            skill_id=str(skill.id),
            edge_id=str(edge.id),
        )
        return Response(SkillEdgeSerializer(edge).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Create or update a tenant override for a skill",
        description=(
            "Copy-on-write override of a (usually global) skill for the current tenant: "
            "rename via name, relabel via status, or hide via hidden — without mutating "
            "the shared global row. Requires taxonomy.edit. Audited."
        ),
        request=TenantSkillOverrideSerializer,
        responses=TenantSkillOverrideSerializer,
        tags=["Skills"],
    )
    @action(detail=True, methods=["post"])
    def override(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        tenant_id = get_current_tenant()
        serializer = TenantSkillOverrideSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        override, _created = TenantSkillOverride.objects.update_or_create(
            skill=skill,
            tenant_id=tenant_id,
            defaults=serializer.validated_data,
        )
        audit.record(
            actor=request.user,
            action="skill.override",
            resource=override,
            tenant_id=tenant_id,
            skill_id=str(skill.id),
        )
        return Response(TenantSkillOverrideSerializer(override).data)

    @extend_schema(
        summary="Publish a skill",
        description=(
            "Transition a draft tenant skill to published. Global skills are read-only "
            "to tenants. Requires taxonomy.edit. Audited."
        ),
        request=None,
        responses=SkillSerializer,
        tags=["Skills"],
    )
    @action(detail=True, methods=["post"])
    def publish(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        self._reject_global(skill)
        published = services.publish_skill(skill, request.user)
        return Response(self.get_serializer(published).data)


@extend_schema_view(
    list=extend_schema(summary="List my skill declarations", tags=["Skills"]),
    create=extend_schema(summary="Declare a skill", tags=["Skills"]),
    destroy=extend_schema(
        summary="Remove a skill declaration",
        tags=["Skills"],
        # The queryset needs the caller's membership, so the id type can't be inferred.
        parameters=[OpenApiParameter("id", OpenApiTypes.UUID, OpenApiParameter.PATH)],
    ),
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


@extend_schema_view(
    list=extend_schema(summary="List verified skill assertions", tags=["Skills"]),
    create=extend_schema(summary="Record a verified skill assertion", tags=["Skills"]),
)
@extend_schema(tags=["Skills"])
class SkillAssertionViewSet(
    IdempotentCreateMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    The verified tier (``skill.verify``). Recording an assertion pins the skill's current
    ``version`` and stamps ``verified_by``/``verified_at``. This is the ONLY source the
    readiness engine reads — self-declarations never gate readiness.

    Create is idempotent via the ``Idempotency-Key`` header; writes are audited.
    """

    serializer_class = SkillAssertionSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = VERIFY_CAPABILITY

    def get_queryset(self) -> Any:
        # Tenant-scoped manager: only the current tenant's assertions are reachable.
        return SkillAssertion.objects.select_related("skill", "membership").order_by("-created_at")

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(
            request, lambda: super(SkillAssertionViewSet, self).create(request)
        )

    def perform_create(self, serializer: Any) -> None:
        from django.utils import timezone

        tenant_id = get_current_tenant()
        skill = serializer.validated_data["skill"]
        assertion = serializer.save(
            tenant_id=tenant_id,
            skill_version=skill.version,  # pin the version judged
            verified_by=self.request.user,
            verified_at=timezone.now(),
        )
        audit.record(
            actor=self.request.user,
            action="skill.assertion.record",
            resource=assertion,
            tenant_id=tenant_id,
            skill_id=str(skill.id),
            level=assertion.level,
        )
        # Part B2 hook: recompute readiness for this membership from the verified tier.
        try:
            from apps.profiles.services import recompute_for_membership

            recompute_for_membership(assertion.membership)
        except Exception:  # noqa: BLE001
            # Non-fatal: readiness recompute failure must not break the assertion write.
            import logging

            logging.getLogger(__name__).exception(
                "readiness recompute failed after assertion write"
            )
