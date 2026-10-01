"""
Member CSV import — dry-run diff + commit.

CSV columns: ``email,display_name,org_unit_path,role,employee_ref``.

``build_diff`` parses the rows and classifies each as an *add* (no membership for
that email in the tenant yet), an *update* (membership exists; display_name /
org_unit / employee_ref may change), or an *error* (missing email, unknown role,
unknown org unit). It writes nothing. ``apply_diff`` performs the adds/updates
inside a single transaction and audits once.

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

from apps.authz.models import Role, RoleGrant
from apps.identity.models import Membership, OrgUnit

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
        else:
            diff.adds.append(entry)

    return diff


@transaction.atomic
def apply_diff(diff: ImportDiff, tenant_id: Any, actor: Any) -> dict[str, Any]:
    """Apply adds + updates inside one transaction and audit once."""
    from core import audit

    person_model = get_user_model()
    roles_by_name = {r.name: r for r in Role.objects.all()}
    units_by_path = {u.path: u for u in OrgUnit.objects.all() if u.path}

    for entry in [*diff.adds, *diff.updates]:
        person = person_model.objects.filter(email=entry["email"]).first()
        if person is None:
            person = person_model.objects.create_user(
                email=entry["email"],
                display_name=entry["display_name"] or entry["email"],
            )
            person.set_unusable_password()
            person.save(update_fields=["password"])

        org_unit = units_by_path.get(entry["org_unit_path"]) if entry["org_unit_path"] else None
        membership, _ = Membership.objects.update_or_create(
            person=person,
            tenant_id=tenant_id,
            defaults={
                "status": "active",
                "employee_ref": entry["employee_ref"],
                "org_unit": org_unit,
            },
        )

        role = roles_by_name.get(entry["role"]) if entry["role"] else None
        if role is not None:
            RoleGrant.objects.get_or_create(
                tenant_id=tenant_id,
                principal_type="person",
                principal_id=person.id,
                role=role,
            )

    audit.record(
        actor=actor,
        action="member.import",
        tenant_id=tenant_id,
        adds=len(diff.adds),
        updates=len(diff.updates),
        errors=len(diff.errors),
    )
    return diff.as_dict()
