"""
Views for the profiles app.

Endpoints:
- /api/profiles/tracks/            CRUD (jobprofile.edit)
- /api/profiles/job-profiles/      CRUD (jobprofile.edit)
  + POST /job-profiles/{id}/requirements/          add requirement
  + DELETE /job-profiles/{id}/requirements/{req}/  remove requirement
  + POST /job-profiles/{id}/publish/               publish (versioned)
- /api/profiles/me/readiness/      learner gap view (skill.claim.submit)
- /api/profiles/readiness/         team snapshots (report.org.view)
- /api/profiles/heatmap/           members x core reqs grid (report.org.view)
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ParseError, PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.profiles import services
from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot, Track
from apps.profiles.serializers import (
    JobProfileSerializer,
    ProfileRequirementSerializer,
    ReadinessSnapshotSerializer,
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
)
class MeReadinessView(APIView):
    """
    Learner gap view — the caller's readiness against a target job profile.

    Reads verified assertions (the only readiness source). Computes on demand
    if no snapshot exists. Requires ``skill.claim.submit``.
    """

    required_capability = "skill.claim.submit"

    def get_permissions(self) -> list[Any]:
        from core.permissions import HasCapability

        perms = [perm() for perm in super().permission_classes]
        perms.append(HasCapability())
        return perms

    def get(self, request: Any) -> Response:
        from apps.identity.models import Membership
        from apps.skills.models import SkillAssertion

        target_id = request.query_params.get("target")
        if not target_id:
            raise ParseError("Query parameter 'target' is required.")

        profile = JobProfile.objects.filter(id=target_id).first()
        if profile is None:
            from django.http import Http404

            raise Http404

        # Resolve the caller's membership in this tenant.
        membership = Membership.objects.filter(person=request.user, status="active").first()
        if membership is None:
            raise PermissionDenied("No active membership in this tenant.")

        # Ensure snapshot is up to date.
        snapshot = services.compute_readiness(membership, profile)

        # Build the per-requirement gap list.
        requirements = list(
            ProfileRequirement.objects.filter(job_profile=profile).select_related("skill")
        )
        assertions_by_skill: dict[Any, int] = {
            a.skill_id: a.level for a in SkillAssertion.objects.filter(membership=membership)
        }

        gap_items = []
        for req in requirements:
            assertion_level = assertions_by_skill.get(req.skill_id)
            is_met = assertion_level is not None and assertion_level >= req.min_level

            if is_met:
                req_status = "met"
            elif assertion_level is not None:
                req_status = "close"
            else:
                req_status = "not_started"

            gap = (req.min_level - (assertion_level or 0)) if not is_met else 0

            gap_items.append(
                {
                    "skill_id": str(req.skill_id),
                    "skill_name": req.skill.name,
                    "criticality": req.criticality,
                    "min_level": req.min_level,
                    "current_level": assertion_level,
                    "status": req_status,
                    "_sort_key": (0 if req_status != "met" else 1, gap),
                }
            )

        # Sort: unmet first (closest-to-done = lowest gap = lowest _sort_key[1]),
        # met last.
        gap_items.sort(key=lambda x: x.pop("_sort_key"))

        readiness_pct = int(snapshot.met * 100 / snapshot.total) if snapshot.total > 0 else 0

        return Response(
            {
                "job_profile": str(profile.id),
                "readiness_pct": readiness_pct,
                "met": snapshot.met,
                "total": snapshot.total,
                "requirements": gap_items,
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

    def get_permissions(self) -> list[Any]:
        from core.permissions import HasCapability

        perms = [perm() for perm in APIView.permission_classes]
        perms.append(HasCapability())
        return perms

    def get_queryset(self) -> Any:
        job_profile_id = self.request.query_params.get("job_profile")
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
        OpenApiParameter("org_unit", description="UUID of the root OrgUnit.", type=str),
        OpenApiParameter("job_profile", description="UUID of the target JobProfile.", type=str),
    ],
    tags=["Profiles"],
)
class HeatmapView(APIView):
    """
    Heatmap: members × core requirements grid.

    Members are those with an org_unit whose ``path`` starts with the requested
    org_unit's path (subtree). Each cell is ``{met: bool}`` based on whether a
    ReadinessSnapshot records the skill as not-blocking. Requires ``report.org.view``.
    """

    required_capability = "report.org.view"

    def get_permissions(self) -> list[Any]:
        from core.permissions import HasCapability

        perms = [perm() for perm in super().permission_classes]
        perms.append(HasCapability())
        return perms

    def get(self, request: Any) -> Response:
        from apps.identity.models import Membership, OrgUnit

        org_unit_id = request.query_params.get("org_unit")
        job_profile_id = request.query_params.get("job_profile")

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
