"""
Views for the profiles app.

Endpoints:
- /api/profiles/tracks/            CRUD (jobprofile.edit)
- /api/profiles/job-profiles/      CRUD (jobprofile.edit)
  + POST /job-profiles/{id}/requirements/          add requirement
  + DELETE /job-profiles/{id}/requirements/{req}/  remove requirement
  + POST /job-profiles/{id}/publish/               publish (versioned)
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles import services
from apps.profiles.models import JobProfile, ProfileRequirement, Track
from apps.profiles.serializers import (
    JobProfileSerializer,
    ProfileRequirementSerializer,
    TrackSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

EDIT_CAPABILITY = "jobprofile.edit"


@extend_schema_view(
    list=extend_schema(
        summary="List tracks",
        description="List all career tracks for the current tenant.",
        tags=["Profiles"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a track",
        description="Retrieve a single career track by ID.",
        tags=["Profiles"],
    ),
    create=extend_schema(
        summary="Create a track",
        description="Create a new career track for the current tenant. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
    update=extend_schema(
        summary="Replace a track",
        description="Replace a track's fields. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
    partial_update=extend_schema(
        summary="Update a track",
        description="Partially update a track. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
    destroy=extend_schema(
        summary="Delete a track",
        description="Delete a track. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
)
@extend_schema(tags=["Profiles"])
class TrackViewSet(viewsets.ModelViewSet):
    """
    CRUD for career tracks. All actions require ``jobprofile.edit``.

    Reads are tenant-scoped (scoped manager). Writes are audited.
    """

    serializer_class = TrackSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = EDIT_CAPABILITY

    def get_queryset(self) -> Any:
        return Track.objects.order_by("name")

    def perform_create(self, serializer: Any) -> None:
        tenant_id = get_current_tenant()
        track = serializer.save(tenant_id=tenant_id)
        audit.record(
            actor=self.request.user,
            action="track.create",
            resource=track,
            tenant_id=tenant_id,
            track_id=str(track.id),
        )

    def perform_update(self, serializer: Any) -> None:
        track = serializer.save()
        audit.record(
            actor=self.request.user,
            action="track.update",
            resource=track,
            tenant_id=track.tenant_id,
            track_id=str(track.id),
        )

    def perform_destroy(self, instance: Track) -> None:
        audit.record(
            actor=self.request.user,
            action="track.delete",
            resource=instance,
            tenant_id=instance.tenant_id,
            track_id=str(instance.id),
        )
        instance.delete()


@extend_schema_view(
    list=extend_schema(
        summary="List job profiles",
        description="List all job profiles for the current tenant.",
        tags=["Profiles"],
    ),
    retrieve=extend_schema(
        summary="Retrieve a job profile",
        description="Retrieve a single job profile by ID.",
        tags=["Profiles"],
    ),
    create=extend_schema(
        summary="Create a job profile",
        description=(
            "Create a new job profile (draft). Idempotent via Idempotency-Key header. "
            "Requires jobprofile.edit."
        ),
        tags=["Profiles"],
    ),
    update=extend_schema(
        summary="Replace a job profile",
        description="Replace a job profile's fields. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
    partial_update=extend_schema(
        summary="Update a job profile",
        description="Partially update a job profile. Requires jobprofile.edit.",
        tags=["Profiles"],
    ),
    destroy=extend_schema(
        summary="Retire a job profile",
        description=(
            "Retire a job profile (status=retired). Never deletes — snapshots point at it. "
            "Requires jobprofile.edit."
        ),
        tags=["Profiles"],
    ),
)
@extend_schema(tags=["Profiles"])
class JobProfileViewSet(IdempotentCreateMixin, viewsets.ModelViewSet):
    """
    CRUD for job profiles. All actions require ``jobprofile.edit``.

    Create is idempotent via the ``Idempotency-Key`` header. Reads are
    tenant-scoped. Writes are audited. Publishing and versioning follow the
    same pattern as skills (draft → published; editing published → new version).
    """

    serializer_class = JobProfileSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = EDIT_CAPABILITY

    def get_queryset(self) -> Any:
        return JobProfile.objects.select_related("track").order_by("track", "grade", "version")

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(
            request, lambda: super(JobProfileViewSet, self).create(request)
        )

    def perform_create(self, serializer: Any) -> None:
        tenant_id = get_current_tenant()
        profile = serializer.save(tenant_id=tenant_id, status="draft", version=1)
        audit.record(
            actor=self.request.user,
            action="jobprofile.create",
            resource=profile,
            tenant_id=tenant_id,
            job_profile_id=str(profile.id),
        )

    def perform_update(self, serializer: Any) -> None:
        profile = serializer.save()
        audit.record(
            actor=self.request.user,
            action="jobprofile.update",
            resource=profile,
            tenant_id=profile.tenant_id,
            job_profile_id=str(profile.id),
        )

    def perform_destroy(self, instance: JobProfile) -> None:
        instance.status = "retired"
        instance.save(update_fields=["status", "updated_at"])
        audit.record(
            actor=self.request.user,
            action="jobprofile.retire",
            resource=instance,
            tenant_id=instance.tenant_id,
            job_profile_id=str(instance.id),
        )

    @extend_schema(
        summary="Add a requirement to a job profile",
        description=(
            "Add a skill requirement (min_level, criticality) to this job profile. "
            "Each skill can appear only once per profile. Requires jobprofile.edit. Audited."
        ),
        request=ProfileRequirementSerializer,
        responses=ProfileRequirementSerializer,
        tags=["Profiles"],
    )
    @action(detail=True, methods=["post"], url_path="requirements")
    def add_requirement(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Add a requirement to this job profile."""
        profile = self.get_object()
        tenant_id = get_current_tenant()
        serializer = ProfileRequirementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        requirement = serializer.save(tenant_id=tenant_id, job_profile=profile)
        audit.record(
            actor=request.user,
            action="jobprofile.requirement.add",
            resource=requirement,
            tenant_id=tenant_id,
            job_profile_id=str(profile.id),
            skill_id=str(requirement.skill_id),
        )
        return Response(
            ProfileRequirementSerializer(requirement).data,
            status=status.HTTP_201_CREATED,
        )

    @extend_schema(
        summary="Remove a requirement from a job profile",
        description=(
            "Remove a skill requirement from this job profile by requirement ID. "
            "Requires jobprofile.edit. Audited."
        ),
        responses={204: None},
        tags=["Profiles"],
    )
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"requirements/(?P<req_id>[^/.]+)",
    )
    def remove_requirement(self, request: Any, req_id: str, *args: Any, **kwargs: Any) -> Response:
        """Remove a requirement from this job profile."""
        profile = self.get_object()
        tenant_id = get_current_tenant()
        requirement = ProfileRequirement.objects.filter(
            id=req_id, job_profile=profile
        ).first()
        if requirement is None:
            from django.http import Http404

            raise Http404
        audit.record(
            actor=request.user,
            action="jobprofile.requirement.remove",
            resource=requirement,
            tenant_id=tenant_id,
            job_profile_id=str(profile.id),
            skill_id=str(requirement.skill_id),
        )
        requirement.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Publish a job profile",
        description=(
            "Transition a draft job profile to published. If the profile is already published, "
            "use the edit endpoints to create a new version. Requires jobprofile.edit. Audited."
        ),
        request=None,
        responses=JobProfileSerializer,
        tags=["Profiles"],
    )
    @action(detail=True, methods=["post"])
    def publish(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Publish a draft job profile."""
        profile = self.get_object()
        published = services.publish_job_profile(profile, request.user)
        return Response(self.get_serializer(published).data)
