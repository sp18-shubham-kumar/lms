"""
Learner profile and member offboarding.

Both are addressed by person id and resolve the person's membership in the
active tenant through the tenant-scoped manager, so a person from another tenant
is a plain 404 — never a leak.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.http import Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authz.models import RoleGrant
from apps.identity.models import Membership
from apps.identity.serializers import PersonProfileSerializer
from apps.skills.models import SelfDeclaredSkill, SkillAssertion
from apps.skills.services import effective_skill_names
from core import audit
from core.context import get_current_tenant
from core.permissions import HasCapability, can

DIRECTORY_CAPABILITY = "directory.view"
REPORT_CAPABILITY = "report.org.view"
OFFBOARD_CAPABILITY = "member.offboard"


def _active_membership(person_id: Any) -> Membership:
    membership = (
        Membership.objects.filter(person_id=person_id, status="active")
        .select_related("person", "org_unit")
        .first()
    )
    if membership is None:
        raise Http404
    return membership


@extend_schema(
    summary="Learner profile",
    description=(
        "A member's profile in the active tenant: person, org unit, declared skills, "
        "verified skills and readiness snapshots. Any member may read their own "
        "profile (also at `people/me/`); reading someone else's requires "
        "directory.view. Readiness is only included for the caller's own profile or "
        "with report.org.view."
    ),
    tags=["Identity"],
    responses=PersonProfileSerializer,
)
class PersonProfileView(APIView):
    def get(self, request: Any, person_id: Any = None) -> Response:
        # ``people/me/`` routes here without a person_id.
        person_id = person_id or request.user.id
        is_self = str(person_id) == str(request.user.id)
        if not is_self and not can(request.user, DIRECTORY_CAPABILITY):
            raise PermissionDenied("You do not have the capability required for this action.")

        tenant_id = get_current_tenant()
        membership = _active_membership(person_id)
        declared = list(
            SelfDeclaredSkill.objects.filter(membership=membership).select_related("skill")
        )
        verified = list(
            SkillAssertion.objects.filter(membership=membership)
            .select_related("skill")
            .order_by("-verified_at")
        )
        names = effective_skill_names(
            tenant_id, [d.skill for d in declared] + [v.skill for v in verified]
        )

        readiness: list[dict[str, Any]] = []
        if is_self or can(request.user, REPORT_CAPABILITY):
            for snap in membership.readiness_snapshots.select_related("job_profile").order_by(
                "job_profile__title"
            ):
                readiness.append(
                    {
                        "job_profile_id": snap.job_profile_id,
                        "job_profile_name": snap.job_profile.title,
                        "met": snap.met,
                        "total": snap.total,
                        "readiness_pct": snap.readiness_pct,
                        "computed_at": snap.computed_at,
                    }
                )

        org_unit = membership.org_unit
        payload = {
            "id": membership.person.id,
            "email": membership.person.email,
            "display_name": membership.person.display_name,
            "status": membership.status,
            "joined_at": membership.joined_at,
            "org_unit": (
                {"id": org_unit.id, "name": org_unit.name, "path": org_unit.path}
                if org_unit
                else None
            ),
            "declared": sorted(
                (
                    {
                        "skill_id": d.skill_id,
                        "skill_name": names[d.skill_id],
                        "level": d.level,
                        "note": d.note,
                    }
                    for d in declared
                ),
                key=lambda row: row["skill_name"].lower(),
            ),
            "verified": [
                {
                    "skill_id": v.skill_id,
                    "skill_name": names[v.skill_id],
                    "level": v.level,
                    "verified_at": v.verified_at,
                }
                for v in verified
            ],
            "readiness": readiness,
        }
        return Response(PersonProfileSerializer(payload).data)


@extend_schema(
    summary="Offboard a member",
    description=(
        "End the person's membership in the active tenant: status becomes `ended`, "
        "`ended_at` is stamped, and every role grant they hold here is revoked. The "
        "person disappears from the directory and tenant reports. Their verified "
        "history is kept. You cannot offboard yourself. Gated by member.offboard."
    ),
    tags=["Identity"],
    request=None,
    responses={204: None},
)
class MemberOffboardView(APIView):
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = OFFBOARD_CAPABILITY

    @transaction.atomic
    def post(self, request: Any, person_id: Any) -> Response:
        if str(person_id) == str(request.user.id):
            raise ValidationError("You cannot offboard yourself.")
        tenant_id = get_current_tenant()
        membership = _active_membership(person_id)
        membership.status = "ended"
        membership.ended_at = timezone.now()
        membership.save(update_fields=["status", "ended_at", "updated_at"])
        revoked, _ = RoleGrant.objects.filter(
            principal_type="person", principal_id=membership.person_id
        ).delete()
        audit.record(
            actor=request.user,
            action="member.offboard",
            resource=membership,
            tenant_id=tenant_id,
            person_id=str(membership.person_id),
            grants_revoked=revoked,
        )
        return Response(status=204)
