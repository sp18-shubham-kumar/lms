from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
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
    ClaimRejectSerializer,
    ClaimVerifySerializer,
    SelfDeclaredSkillSerializer,
    SkillAssertionSerializer,
    SkillClaimSerializer,
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
_WRITE_ACTIONS = {
    "create",
    "update",
    "partial_update",
    "destroy",
    "edges",
    "override",
    "publish",
    "new_version",
}
# The levels action gates per-method: GET reads (directory.view), PUT writes (taxonomy.edit).


def _capability_for(action: str | None) -> str:
    return WRITE_CAPABILITY if action in _WRITE_ACTIONS else READ_CAPABILITY


def _validation_error(exc: DjangoValidationError) -> ValidationError:
    return ValidationError(exc.messages)


@extend_schema_view(
    list=extend_schema(summary="List skill domains", tags=["Skills"]),
    retrieve=extend_schema(summary="Retrieve a skill domain", tags=["Skills"]),
    create=extend_schema(summary="Create a tenant skill domain", tags=["Skills"]),
    update=extend_schema(summary="Replace a tenant skill domain", tags=["Skills"]),
    partial_update=extend_schema(summary="Update a tenant skill domain", tags=["Skills"]),
)
@extend_schema(tags=["Skills"])
class SkillDomainViewSet(
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.ReadOnlyModelViewSet,
):
    """
    Skill domains visible to the tenant (globals + tenant rows).

    Reads need ``directory.view``; create/edit need ``taxonomy.edit`` and only ever
    touch the current tenant's own domains — globals are read-only. Audited.
    """

    serializer_class = SkillDomainSerializer
    required_capability = READ_CAPABILITY

    def get_permissions(self) -> list[Any]:
        self.required_capability = _capability_for(self.action)
        return [*(perm() for perm in APIView.permission_classes), HasCapability()]

    def get_queryset(self) -> Any:
        # .visible() = globals (tenant NULL) ∪ current tenant rows (fail-closed).
        return SkillDomain.objects.visible().order_by("sort", "name")

    def perform_create(self, serializer: Any) -> None:
        tenant_id = get_current_tenant()
        domain = serializer.save(tenant_id=tenant_id)
        audit.record(
            actor=self.request.user,
            action="skill.domain.create",
            resource=domain,
            tenant_id=tenant_id,
        )

    def perform_update(self, serializer: Any) -> None:
        if serializer.instance.tenant_id is None:
            raise PermissionDenied("Global domains are read-only to tenants.")
        domain = serializer.save()
        audit.record(
            actor=self.request.user,
            action="skill.domain.update",
            resource=domain,
            tenant_id=domain.tenant_id,
        )


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
            capability = _capability_for(self.action)
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
        try:
            services.ensure_editable(serializer.instance)
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
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

        self._reject_global(skill)
        try:
            services.ensure_editable(skill)
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
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
            # visible(): a global skill's edges include only globals + this tenant's own.
            qs = SkillEdge.objects.visible().filter(from_skill=skill)
            return Response({"edges": SkillEdgeSerializer(qs, many=True).data})

        self._reject_global(skill)

        if request.method == "DELETE":
            edge_id = request.query_params.get("edge")
            edge = SkillEdge.objects.visible().filter(id=edge_id, from_skill=skill).first()
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
            raise _validation_error(exc) from exc
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

    @extend_schema(
        summary="List a skill's versions",
        description="Every version of the skill (same tenant + slug), newest first.",
        responses=SkillSerializer(many=True),
        tags=["Skills"],
    )
    @action(detail=True, methods=["get"])
    def versions(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        rows = services.versions_of(skill)
        return Response({"versions": SkillSerializer(rows, many=True).data})

    @extend_schema(
        summary="Start a new draft version of a skill",
        description=(
            "Copy a published tenant skill and its rubric into a new draft version. The "
            "prior version stays immutable (assertions pin it). Requires taxonomy.edit."
        ),
        request=None,
        responses={201: SkillSerializer},
        tags=["Skills"],
    )
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        skill = self.get_object()
        self._reject_global(skill)
        if skill.status != "published":
            raise ValidationError("Only a published skill can be versioned.")
        draft = services.new_version_from(skill, request.user)
        return Response(self.get_serializer(draft).data, status=status.HTTP_201_CREATED)


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
        data = serializer.validated_data
        serializer.instance = services.record_assertion(
            membership=data["membership"],
            skill=data["skill"],
            level=data["level"],
            actor=self.request.user,
            tenant_id=get_current_tenant(),
            note=data.get("note", ""),
            skill_level=data.get("skill_level"),
        )


CLAIM_STATUS_FILTERS = {*SelfDeclaredSkill.ReviewStatus.values, "all"}


@extend_schema_view(
    list=extend_schema(
        summary="List skill claims for review",
        tags=["Skills"],
        parameters=[
            OpenApiParameter(
                "status",
                OpenApiTypes.STR,
                enum=sorted(CLAIM_STATUS_FILTERS),
                description="Review status to list (default: pending).",
            )
        ],
    ),
    retrieve=extend_schema(summary="Retrieve a skill claim", tags=["Skills"]),
)
@extend_schema(tags=["Skills"])
class SkillClaimViewSet(viewsets.ReadOnlyModelViewSet):
    """
    The verifier's queue (``skill.verify``): members' self-declared claims in this
    tenant. Verifying records a :class:`SkillAssertion` — the only readiness input —
    and rejecting records a reason. Nobody reviews their own claim. Audited.
    """

    serializer_class = SkillClaimSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = VERIFY_CAPABILITY

    def get_queryset(self) -> Any:
        qs = SelfDeclaredSkill.objects.select_related("skill", "membership__person").order_by(
            "created_at"
        )
        if self.action != "list":
            return qs
        wanted = self.request.query_params.get("status", SelfDeclaredSkill.ReviewStatus.PENDING)
        if wanted not in CLAIM_STATUS_FILTERS:
            raise ValidationError({"status": f"Must be one of {sorted(CLAIM_STATUS_FILTERS)}."})
        return qs if wanted == "all" else qs.filter(review_status=wanted)

    def _review(self, fn: Any, **kwargs: Any) -> Any:
        try:
            return fn(self.get_object(), actor=self.request.user, **kwargs)
        except DjangoValidationError as exc:
            raise _validation_error(exc) from exc
        except DjangoPermissionDenied as exc:
            raise PermissionDenied(str(exc)) from exc

    @extend_schema(
        summary="Verify a skill claim",
        request=ClaimVerifySerializer,
        responses={201: SkillAssertionSerializer},
        tags=["Skills"],
    )
    @action(detail=True, methods=["post"])
    def verify(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        body = ClaimVerifySerializer(data=request.data)
        body.is_valid(raise_exception=True)
        assertion = self._review(services.verify_claim, **body.validated_data)
        return Response(SkillAssertionSerializer(assertion).data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Reject a skill claim",
        request=ClaimRejectSerializer,
        responses=SkillClaimSerializer,
        tags=["Skills"],
    )
    @action(detail=True, methods=["post"])
    def reject(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        body = ClaimRejectSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        claim = self._review(services.reject_claim, **body.validated_data)
        return Response(SkillClaimSerializer(claim).data)
