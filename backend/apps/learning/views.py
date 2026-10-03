"""
Views for the learning app.

Endpoints:
- /api/learning/resources/              CRUD (read: directory.view, write: resource.edit)
    ?skill=<id>  ?kind=<kind>  ?q=<text>  ?status=<status> (editors only)
- /api/learning/me/progress/            the caller's own progress (skill.claim.submit)
    POST {resource} starts, PATCH {completed_modules?, status?} advances/resets
- /api/learning/me/recommendations/     resources for the caller's gaps (skill.claim.submit)
    ?target=<job profile id>
"""

from __future__ import annotations

from typing import Any

from django.http import Http404
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.learning import services
from apps.learning.models import LearningProgress, LearningResource
from apps.learning.serializers import (
    LearningProgressSerializer,
    LearningResourceSerializer,
    ProgressStartSerializer,
    ProgressUpdateSerializer,
    RecommendationsSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.params import uuid_param
from core.permissions import HasCapability, can

READ_CAPABILITY = "directory.view"
EDIT_CAPABILITY = "resource.edit"
LEARN_CAPABILITY = "skill.claim.submit"

_WRITE_ACTIONS = {"create", "update", "partial_update", "destroy"}


def _current_membership(request: Any) -> Any:
    from apps.identity.models import Membership

    membership = Membership.objects.filter(person=request.user, status="active").first()
    if membership is None:
        raise PermissionDenied("No active membership in this tenant.")
    return membership


@extend_schema_view(
    list=extend_schema(
        summary="List learning resources",
        description=(
            "Published resources for the current tenant. Editors (resource.edit) also see "
            "draft and archived resources, and may filter on them with ?status."
        ),
        parameters=[
            OpenApiParameter("skill", str, description="Only resources linked to this skill."),
            OpenApiParameter("kind", str, description="course | article | video | book | other"),
            OpenApiParameter("q", str, description="Case-insensitive title search."),
            OpenApiParameter("status", str, description="draft | published | archived (editors)."),
        ],
    ),
    retrieve=extend_schema(summary="Retrieve a learning resource"),
    create=extend_schema(
        summary="Create a learning resource",
        description="Idempotent via the Idempotency-Key header. Requires resource.edit.",
    ),
    update=extend_schema(
        summary="Replace a learning resource", description="Requires resource.edit."
    ),
    partial_update=extend_schema(
        summary="Update a learning resource",
        description="Sending `skills` replaces every skill link. Requires resource.edit.",
    ),
    destroy=extend_schema(
        summary="Archive a learning resource",
        description=(
            "Sets status=archived. Never deletes — learner progress points at it. "
            "Requires resource.edit."
        ),
    ),
)
@extend_schema(tags=["Learning"])
class LearningResourceViewSet(IdempotentCreateMixin, viewsets.ModelViewSet):
    """
    The tenant's resource library. Reads require ``directory.view``; writes require
    ``resource.edit``. Learners only ever see published resources. Writes are audited.
    """

    serializer_class = LearningResourceSerializer
    required_capability = EDIT_CAPABILITY

    def get_permissions(self) -> list[Any]:
        self.required_capability = (
            EDIT_CAPABILITY if self.action in _WRITE_ACTIONS else READ_CAPABILITY
        )
        return [*(perm() for perm in APIView.permission_classes), HasCapability()]

    def get_queryset(self) -> Any:
        qs = LearningResource.objects.prefetch_related("skill_links__skill")
        params = self.request.query_params
        if can(self.request.user, EDIT_CAPABILITY):
            if params.get("status"):
                qs = qs.filter(status=params["status"])
        else:
            qs = qs.filter(status="published")
        skill_id = uuid_param(self.request, "skill")
        if skill_id:
            qs = qs.filter(skill_links__skill_id=skill_id)
        if params.get("kind"):
            qs = qs.filter(kind=params["kind"])
        if params.get("q"):
            qs = qs.filter(title__icontains=params["q"])
        return qs.distinct().order_by("title")

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(
            request, lambda: super(LearningResourceViewSet, self).create(request)
        )

    def _audit(self, action: str, resource: LearningResource) -> None:
        audit.record(
            actor=self.request.user,
            action=action,
            resource=resource,
            tenant_id=resource.tenant_id,
            status=resource.status,
            skill_ids=[str(link.skill_id) for link in resource.skill_links.all()],
        )

    def perform_create(self, serializer: Any) -> None:
        self._audit("resource.create", serializer.save(tenant_id=get_current_tenant()))

    def perform_update(self, serializer: Any) -> None:
        self._audit("resource.update", serializer.save())

    def perform_destroy(self, instance: LearningResource) -> None:
        instance.status = "archived"
        instance.save(update_fields=["status", "updated_at"])
        self._audit("resource.archive", instance)


_PROGRESS_ID = OpenApiParameter(
    "id", OpenApiTypes.UUID, OpenApiParameter.PATH, description="ID of the progress row."
)


@extend_schema_view(
    list=extend_schema(summary="List my learning progress"),
    retrieve=extend_schema(summary="Retrieve my progress on a resource", parameters=[_PROGRESS_ID]),
    create=extend_schema(
        summary="Start a learning resource",
        description=(
            "Start a published resource. Idempotent: starting a resource you already have "
            "progress on returns that row (200) instead of creating another (201). "
            "Self-reported — never creates a verified assertion or changes readiness."
        ),
        request=ProgressStartSerializer,
        responses={200: LearningProgressSerializer, 201: LearningProgressSerializer},
    ),
    partial_update=extend_schema(
        summary="Update my progress on a resource",
        description=(
            "Set completed_modules and/or status. Reaching the resource's module count, or "
            "status=completed, completes it; status=not_started resets it."
        ),
        parameters=[_PROGRESS_ID],
        request=ProgressUpdateSerializer,
        responses=LearningProgressSerializer,
    ),
)
@extend_schema(tags=["Learning"])
class MyProgressViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """The caller's own learning progress. A member only ever sees and edits their own rows."""

    serializer_class = LearningProgressSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = LEARN_CAPABILITY
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self) -> Any:
        return LearningProgress.objects.filter(
            membership=_current_membership(self.request)
        ).select_related("resource")

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        body = ProgressStartSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        progress, created = services.start_progress(
            _current_membership(request), body.validated_data["resource"], request.user
        )
        return Response(
            LearningProgressSerializer(progress).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    def partial_update(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        body = ProgressUpdateSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        progress = services.update_progress(self.get_object(), request.user, **body.validated_data)
        return Response(LearningProgressSerializer(progress).data)


@extend_schema(
    summary="Resources for my gaps against a job profile",
    description=(
        "For each requirement of the target job profile the caller hasn't met (by verified "
        "level), the published resources that teach that skill beyond the caller's current "
        "level, with the caller's progress on each. Requires skill.claim.submit."
    ),
    parameters=[
        OpenApiParameter("target", str, required=True, description="UUID of the target JobProfile.")
    ],
    responses=RecommendationsSerializer,
    tags=["Learning"],
)
class MyRecommendationsView(APIView):
    required_capability = LEARN_CAPABILITY

    permission_classes = [*APIView.permission_classes, HasCapability]

    def get(self, request: Any) -> Response:
        from apps.profiles.models import JobProfile

        target_id = uuid_param(request, "target", required=True)
        profile = JobProfile.objects.filter(id=target_id).first()
        if profile is None:
            raise Http404
        gaps = services.recommend_for_gaps(_current_membership(request), profile)
        return Response(RecommendationsSerializer({"job_profile": profile.id, "gaps": gaps}).data)
