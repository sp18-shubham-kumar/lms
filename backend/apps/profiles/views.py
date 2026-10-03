"""
Views for the profiles app.

Endpoints:
- /api/profiles/tracks/            CRUD (read: directory.view, write: jobprofile.edit)
- /api/profiles/job-profiles/      CRUD (read: directory.view, write: jobprofile.edit)
  + GET  /job-profiles/{id}/requirements/          list requirements
  + POST /job-profiles/{id}/requirements/          add requirement (draft only)
  + DELETE /job-profiles/{id}/requirements/{req}/  remove requirement (draft only)
  + POST /job-profiles/{id}/publish/               publish (versioned)
  + POST /job-profiles/{id}/new-version/           open a new draft of a published profile
- /api/profiles/me/readiness/      learner gap view (skill.claim.submit)
- /api/profiles/members/{membership}/readiness/  one member's gap (report.org.view)
- /api/profiles/readiness/         team snapshots (report.org.view)
- /api/profiles/heatmap/           members x core reqs grid (report.org.view)
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import APIException, ParseError, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles import services
from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot, Track
from apps.profiles.serializers import (
    HeatmapSerializer,
    JobProfileSerializer,
    MemberReadinessSerializer,
    MeReadinessSerializer,
    ProfileRequirementSerializer,
    ReadinessSnapshotSerializer,
    TrackSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.params import uuid_param
from core.permissions import HasCapability

EDIT_CAPABILITY = "jobprofile.edit"
READ_CAPABILITY = "directory.view"

# Reads (list/retrieve) are open to any directory viewer — a learner needs to
# see the career ladder to pick a target grade. Writes require jobprofile.edit.
# Mirrors the read/write split in the skills app.
_WRITE_ACTIONS = {
    "create",
    "update",
    "partial_update",
    "destroy",
    "add_requirement",
    "remove_requirement",
    "publish",
    "new_version",
}


class ProfileConflict(APIException):
    """409: the profile's lifecycle state doesn't allow this change."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "profile_not_editable"
    default_detail = "This job profile can't be changed in its current state."


class TrackInUse(APIException):
    """409: a track still holds job profiles (any status), so it can't be deleted."""

    status_code = status.HTTP_409_CONFLICT
    default_code = "track_in_use"
    default_detail = "This track still has job profiles. Retire or move them first."


def _ensure_editable(profile: JobProfile) -> None:
    try:
        services.ensure_editable(profile)
    except services.ProfileNotEditable as exc:
        raise ProfileConflict(str(exc)) from exc


def _profile_permissions(view: Any) -> list[Any]:
    """Read actions require directory.view; write actions require jobprofile.edit."""
    view.required_capability = EDIT_CAPABILITY if view.action in _WRITE_ACTIONS else READ_CAPABILITY
    perms: list[Any] = [perm() for perm in APIView.permission_classes]
    perms.append(HasCapability())
    return perms


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
        description=(
            "Delete a track. 409 (track_in_use) while it still has job profiles, "
            "retired ones included. Requires jobprofile.edit."
        ),
        tags=["Profiles"],
    ),
)
@extend_schema(tags=["Profiles"])
class TrackViewSet(viewsets.ModelViewSet):
    """
    CRUD for career tracks. Reads require ``directory.view``; writes require
    ``jobprofile.edit``.

    Reads are tenant-scoped (scoped manager). Writes are audited.
    """

    serializer_class = TrackSerializer
    required_capability = EDIT_CAPABILITY

    def get_permissions(self) -> list[Any]:
        return _profile_permissions(self)

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
        # JobProfile.track is PROTECT; check up front so the caller gets a 409, not a 500.
        if instance.job_profiles.exists():
            raise TrackInUse()
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
        description="List job profiles for the current tenant, optionally filtered.",
        parameters=[
            OpenApiParameter(
                "status",
                description="Only profiles in this status (draft, published, retired).",
                required=False,
                type=str,
            ),
            OpenApiParameter(
                "track", description="Only profiles in this track (UUID).", required=False, type=str
            ),
        ],
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
        description=(
            "Replace a draft job profile's fields. Published/retired versions return 409. "
            "Requires jobprofile.edit."
        ),
        tags=["Profiles"],
    ),
    partial_update=extend_schema(
        summary="Update a job profile",
        description=(
            "Partially update a draft job profile. Published/retired versions return 409. "
            "Requires jobprofile.edit."
        ),
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
    CRUD for job profiles. Reads (list/retrieve) require ``directory.view`` so a
    learner can browse the career ladder and pick a target grade; writes require
    ``jobprofile.edit``.

    Create is idempotent via the ``Idempotency-Key`` header. Reads are
    tenant-scoped. Writes are audited. Publishing and versioning follow the
    same pattern as skills (draft → published; editing published → new version).
    """

    serializer_class = JobProfileSerializer
    required_capability = EDIT_CAPABILITY

    def get_permissions(self) -> list[Any]:
        return _profile_permissions(self)

    def get_queryset(self) -> Any:
        qs = JobProfile.objects.select_related("track")
        if self.action == "list":
            status_filter = self.request.query_params.get("status")
            track_filter = uuid_param(self.request, "track")
            if status_filter:
                qs = qs.filter(status=status_filter)
            if track_filter:
                qs = qs.filter(track_id=track_filter)
        return qs.order_by("track__name", "grade", "title", "version")

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
        _ensure_editable(serializer.instance)
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
            "Each skill can appear only once per profile. Draft profiles only (409 "
            "otherwise). Requires jobprofile.edit. Audited."
        ),
        request=ProfileRequirementSerializer,
        responses=ProfileRequirementSerializer,
        tags=["Profiles"],
    )
    @action(detail=True, methods=["post"], url_path="requirements")
    def add_requirement(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Add a requirement to this job profile."""
        profile = self.get_object()
        _ensure_editable(profile)
        tenant_id = get_current_tenant()
        serializer = ProfileRequirementSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if ProfileRequirement.objects.filter(
            job_profile=profile, skill=serializer.validated_data["skill"]
        ).exists():
            raise ProfileConflict("This skill is already a requirement of this profile.")
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
        summary="List a job profile's requirements",
        description="List the skill requirements of this job profile. Requires directory.view.",
        request=None,
        responses=ProfileRequirementSerializer(many=True),
        tags=["Profiles"],
    )
    @add_requirement.mapping.get
    def list_requirements(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """List this job profile's requirements, by skill name."""
        profile = self.get_object()
        requirements = (
            ProfileRequirement.objects.filter(job_profile=profile)
            .select_related("skill")
            .order_by("skill__name")
        )
        return Response(ProfileRequirementSerializer(requirements, many=True).data)

    @extend_schema(
        summary="Remove a requirement from a job profile",
        description=(
            "Remove a skill requirement from this job profile by requirement ID. "
            "Draft profiles only (409 otherwise). Requires jobprofile.edit. Audited."
        ),
        parameters=[
            OpenApiParameter(
                "req_id",
                OpenApiTypes.UUID,
                OpenApiParameter.PATH,
                description="ID of the ProfileRequirement to remove.",
            )
        ],
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
        _ensure_editable(profile)
        tenant_id = get_current_tenant()
        requirement = ProfileRequirement.objects.filter(id=req_id, job_profile=profile).first()
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
            "Transition a draft job profile to published. Publishing a published profile is a "
            "no-op; a retired one returns 409. To change a published profile, open a new "
            "version. Requires jobprofile.edit. Audited."
        ),
        request=None,
        responses=JobProfileSerializer,
        tags=["Profiles"],
    )
    @action(detail=True, methods=["post"])
    def publish(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Publish a draft job profile."""
        profile = self.get_object()
        try:
            published = services.publish_job_profile(profile, request.user)
        except services.ProfileNotEditable as exc:
            raise ProfileConflict(str(exc)) from exc
        return Response(self.get_serializer(published).data)

    @extend_schema(
        summary="Open a new version of a job profile",
        description=(
            "Create the next draft version of a published (or retired) job profile, copying "
            "its requirements. The prior version is retained unchanged. 409 if the profile is "
            "itself a draft or the profile already has an open draft. Requires "
            "jobprofile.edit. Audited."
        ),
        request=None,
        responses={201: JobProfileSerializer},
        tags=["Profiles"],
    )
    @action(detail=True, methods=["post"], url_path="new-version")
    def new_version(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        """Open the next draft version of this profile."""
        profile = self.get_object()
        try:
            draft = services.new_version_from_profile(profile, request.user)
        except services.ProfileNotEditable as exc:
            raise ProfileConflict(str(exc)) from exc
        return Response(self.get_serializer(draft).data, status=status.HTTP_201_CREATED)


# ─── Readiness / gap / heatmap views ─────────────────────────────────────────


@extend_schema(
    summary="My gap against a job profile",
    description=(
        "Return the caller's gap for a target job profile. For each requirement, "
        "returns skill name, required level, current verified assertion level (or null), "
        "and status (met/close/not_started). Results are sorted with unmet requirements "
        "first (closest-to-done = lowest gap) and met requirements last. "
        "Includes overall readiness_pct (met/total * 100 for core requirements). "
        "Requires skill.claim.submit."
    ),
    parameters=[
        OpenApiParameter(
            "target",
            description="UUID of the target JobProfile.",
            required=True,
            type=str,
        )
    ],
    tags=["Profiles"],
    responses=MeReadinessSerializer,
)
class MeReadinessView(APIView):
    """
    Learner gap view — the caller's readiness against a target job profile.

    Reads verified assertions (the only readiness source). Computes on demand
    if no snapshot exists. Requires ``skill.claim.submit``.
    """

    required_capability = "skill.claim.submit"

    permission_classes = [*APIView.permission_classes, HasCapability]

    def get(self, request: Any) -> Response:
        from apps.identity.models import Membership

        profile = _target_profile(request)

        # Resolve the caller's membership in this tenant.
        membership = Membership.objects.filter(person=request.user, status="active").first()
        if membership is None:
            raise PermissionDenied("No active membership in this tenant.")

        return Response(services.gap_report(membership, profile))


def _target_profile(request: Any) -> JobProfile:
    """The JobProfile named by the required ``target`` query parameter (tenant-scoped)."""
    from django.http import Http404

    target_id = uuid_param(request, "target", required=True)
    profile = JobProfile.objects.filter(id=target_id).first()
    if profile is None:
        raise Http404
    return profile


@extend_schema(
    summary="One member's gap against a job profile",
    description=(
        "The same gap report as me/readiness, for another active member of the caller's "
        "tenant — the manager's drill-down from the team heatmap. Requires report.org.view."
    ),
    parameters=[
        OpenApiParameter(
            "membership_id",
            OpenApiTypes.UUID,
            OpenApiParameter.PATH,
            description="Membership whose readiness to report.",
        ),
        OpenApiParameter(
            "target",
            description="UUID of the target JobProfile.",
            required=True,
            type=str,
        ),
    ],
    tags=["Profiles"],
    responses=MemberReadinessSerializer,
)
class MemberReadinessView(APIView):
    """A manager's view of one member's readiness. Tenant-scoped; ``report.org.view``."""

    required_capability = "report.org.view"

    permission_classes = [*APIView.permission_classes, HasCapability]

    def get(self, request: Any, membership_id: Any) -> Response:
        from django.http import Http404

        from apps.identity.models import Membership

        membership = (
            Membership.objects.filter(id=membership_id, status="active")
            .select_related("person")
            .first()
        )
        if membership is None:
            raise Http404
        profile = _target_profile(request)
        return Response(
            {
                **services.gap_report(membership, profile),
                "membership_id": str(membership.id),
                "display_name": membership.person.display_name,
            }
        )


@extend_schema(
    summary="Team readiness for a job profile",
    description=(
        "List ReadinessSnapshots for all active memberships in the caller's tenant "
        "for the given job profile. Requires report.org.view."
    ),
    parameters=[
        OpenApiParameter(
            "job_profile",
            description="UUID of the target JobProfile.",
            required=True,
            type=str,
        )
    ],
    tags=["Profiles"],
)
class TeamReadinessView(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Team-level readiness: all active members' snapshots for a given job profile.
    Tenant-scoped (reads via scoped manager). Requires ``report.org.view``.
    """

    serializer_class = ReadinessSnapshotSerializer
    required_capability = "report.org.view"

    permission_classes = [*APIView.permission_classes, HasCapability]

    def get_queryset(self) -> Any:
        job_profile_id = uuid_param(self.request, "job_profile")
        qs = ReadinessSnapshot.objects.select_related("membership__person")
        if job_profile_id:
            qs = qs.filter(job_profile_id=job_profile_id)
        return qs.order_by("-met")


@extend_schema(
    summary="Heatmap of member readiness",
    description=(
        "Return a grid of members (rows) × core requirements (columns). "
        "Each cell is {met: bool}. Scoped to the org_unit subtree "
        "(members whose org_unit path starts with the target org_unit's path). "
        "Requires report.org.view."
    ),
    parameters=[
        OpenApiParameter(
            "org_unit", description="UUID of the root OrgUnit.", required=True, type=str
        ),
        OpenApiParameter(
            "job_profile", description="UUID of the target JobProfile.", required=True, type=str
        ),
    ],
    tags=["Profiles"],
    responses=HeatmapSerializer,
)
class HeatmapView(APIView):
    """
    Heatmap: members × core requirements grid.

    Members are those with an org_unit whose ``path`` starts with the requested
    org_unit's path (subtree). Each cell is ``{met: bool}`` based on whether a
    ReadinessSnapshot records the skill as not-blocking. Requires ``report.org.view``.
    """

    required_capability = "report.org.view"

    permission_classes = [*APIView.permission_classes, HasCapability]

    def get(self, request: Any) -> Response:
        from apps.identity.models import Membership, OrgUnit

        org_unit_id = uuid_param(request, "org_unit")
        job_profile_id = uuid_param(request, "job_profile")

        if not org_unit_id or not job_profile_id:
            raise ParseError("Query parameters 'org_unit' and 'job_profile' are required.")

        org_unit = OrgUnit.objects.filter(id=org_unit_id).first()
        if org_unit is None:
            from django.http import Http404

            raise Http404

        profile = JobProfile.objects.filter(id=job_profile_id).first()
        if profile is None:
            from django.http import Http404

            raise Http404

        # Subtree: memberships whose org_unit path starts with this unit's path.
        subtree_path = org_unit.path or str(org_unit.id)
        subtree_member_qs = (
            Membership.objects.filter(status="active")
            .filter(
                org_unit__path__startswith=subtree_path,
            )
            .select_related("person", "org_unit")
        )
        # Fall back to direct membership if path not set — include exact org_unit match
        subtree_members = list(
            subtree_member_qs
            | Membership.objects.filter(status="active", org_unit=org_unit).select_related(
                "person", "org_unit"
            )
        )
        # Deduplicate
        seen_ids: set[Any] = set()
        unique_members = []
        for m in subtree_members:
            if m.id not in seen_ids:
                seen_ids.add(m.id)
                unique_members.append(m)

        # Core requirements for this profile (columns).
        core_reqs = list(
            ProfileRequirement.objects.filter(job_profile=profile, criticality="core")
            .select_related("skill")
            .order_by("skill__name")
        )

        # Snapshots for these members.
        snapshot_map: dict[Any, Any] = {
            s.membership_id: s
            for s in ReadinessSnapshot.objects.filter(
                membership__in=unique_members, job_profile=profile
            )
        }
        # Readiness is computed, never assumed: a member with no snapshot yet (they've
        # never opened this target) gets one now rather than rendering as all-unmet.
        unsnapshotted = [m for m in unique_members if m.id not in snapshot_map]
        if unsnapshotted:
            requirements = services.profile_requirements(profile)
            for member in unsnapshotted:
                snapshot_map[member.id] = services.compute_readiness(
                    member, profile, requirements=requirements
                )

        columns = [{"skill_id": str(r.skill_id), "skill_name": r.skill.name} for r in core_reqs]

        rows = []
        for member in unique_members:
            snapshot = snapshot_map.get(member.id)
            blocking_ids: set[Any] = set()
            if snapshot is not None:
                blocking_ids = {str(uid) for uid in snapshot.blocking_skill_ids}
            cells = [
                {"met": str(req.skill_id) not in blocking_ids and snapshot is not None}
                for req in core_reqs
            ]
            rows.append(
                {
                    "membership_id": str(member.id),
                    "display_name": member.person.display_name,
                    "cells": cells,
                }
            )

        return Response({"columns": columns, "rows": rows})
