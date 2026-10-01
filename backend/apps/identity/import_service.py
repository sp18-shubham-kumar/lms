"""
Member CSV import — dry-run diff + commit.

CSV columns: ``email,display_name,org_unit_path,role,employee_ref``.

``build_diff`` parses the rows and classifies each as an *add* (no membership for
that email in the tenant yet), an *update* (membership exists), or an *error*
(missing email, missing role on a new email, unknown role, unknown org unit, or
an invitation already pending). It writes nothing. ``apply_diff`` invites each
add with the same pending invitation a member invite uses, and updates an
existing member's org unit and employee ref. New emails do not get a membership
or a usable password until they accept.

All reads/writes are tenant-scoped via ``Model.objects`` (the caller runs inside
the active tenant's context, guaranteed by the request path).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

from apps.authz.models import Role
from apps.identity.invitation_service import InvitationError, create_invitation
from apps.identity.models import Invitation, Membership, OrgUnit

# CSV columns consumed by the importer: email,display_name,org_unit_path,role,employee_ref


@dataclass
class ImportDiff:
    adds: list[dict[str, Any]] = field(default_factory=list)
    updates: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"adds": self.adds, "updates": self.updates, "errors": self.errors}


def parse_rows(raw: str) -> list[dict[str, str]]:
    """Parse a CSV string into a list of dict rows keyed by header."""
    reader = csv.DictReader(io.StringIO(raw))
    return [dict(row) for row in reader]


def build_diff(raw: str, tenant_id: Any) -> ImportDiff:
    """Classify each CSV row into adds / updates / errors. Writes nothing."""
    diff = ImportDiff()
    rows = parse_rows(raw)
    person_model = get_user_model()

    # Preload the tenant's roles + org units for validation (tenant-scoped).
    roles_by_name = {r.name: r for r in Role.objects.all()}
    units_by_path = {u.path: u for u in OrgUnit.objects.all() if u.path}

    for index, row in enumerate(rows, start=1):
        email = (row.get("email") or "").strip().lower()
        if not email or "@" not in email:
            diff.errors.append({"row": index, "reason": "missing or invalid email"})
            continue

        role_name = (row.get("role") or "").strip()
        if role_name and role_name not in roles_by_name:
            diff.errors.append({"row": index, "reason": f"unknown role: {role_name}"})
            continue

        org_unit_path = (row.get("org_unit_path") or "").strip()
        if org_unit_path and org_unit_path not in units_by_path:
            diff.errors.append({"row": index, "reason": f"unknown org_unit_path: {org_unit_path}"})
            continue

        entry = {
            "row": index,
            "email": email,
            "display_name": (row.get("display_name") or "").strip(),
            "org_unit_path": org_unit_path,
            "role": role_name,
            "employee_ref": (row.get("employee_ref") or "").strip(),
        }

        person = person_model.objects.filter(email=email).first()
        has_membership = person is not None and Membership.objects.filter(person=person).exists()
        if has_membership:
            diff.updates.append(entry)
            continue

        if not role_name:
            diff.errors.append({"row": index, "reason": "missing role"})
            continue
        if Invitation.objects.filter(email=email, status=Invitation.Status.PENDING).exists():
            diff.errors.append(
                {"row": index, "reason": "An invitation is already pending for this email."}
            )
            continue
        diff.adds.append(entry)

    return diff


@transaction.atomic
def apply_diff(diff: ImportDiff, tenant_id: Any, actor: Any) -> dict[str, Any]:
    """Invite new emails and update existing members' org unit and employee ref."""
    from core import audit

    person_model = get_user_model()
    units_by_path = {u.path: u for u in OrgUnit.objects.all() if u.path}

    invited: list[dict[str, Any]] = []
    for entry in diff.adds:
        if not entry["role"]:
            diff.errors.append({"row": entry["row"], "reason": "missing role"})
            continue
        try:
            create_invitation(
                email=entry["email"],
                role_name=entry["role"],
                actor=actor,
                tenant_id=tenant_id,
            )
        except InvitationError as exc:
            diff.errors.append({"row": entry["row"], "reason": exc.detail})
            continue
        entry["invited"] = True
        invited.append(entry)
    diff.adds = invited

    updated: list[dict[str, Any]] = []
    for entry in diff.updates:
        person = person_model.objects.filter(email=entry["email"]).first()
        membership = (
            Membership.objects.filter(person=person).first() if person is not None else None
        )
        if membership is None:
            diff.errors.append({"row": entry["row"], "reason": "member not found"})
            continue
        org_unit = units_by_path.get(entry["org_unit_path"]) if entry["org_unit_path"] else None
        membership.employee_ref = entry["employee_ref"]
        membership.org_unit = org_unit
        membership.save(update_fields=["employee_ref", "org_unit", "updated_at"])
        updated.append(entry)
    diff.updates = updated

    audit.record(
        actor=actor,
        action="member.import",
        tenant_id=tenant_id,
        adds=len(diff.adds),
        updates=len(diff.updates),
        errors=len(diff.errors),
    )
    return diff.as_dict()
