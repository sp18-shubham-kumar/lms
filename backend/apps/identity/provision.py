"""Create a tenant and email its first Tenant Admin. Used by the platform operator endpoint."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction

from apps.authz.models import Capability, Role, RoleCapability
from apps.identity.invitation_service import create_invitation
from apps.identity.models import Tenant
from core.context import tenant_context

ADMIN_ROLE = "Tenant Admin"
ADMIN_CAPABILITIES = [
    "directory.view",
    "skill.claim.submit",
    "skill.verify",
    "verifier.grant",
    "member.invite",
    "member.offboard",
    "credential.revoke",
    "taxonomy.edit",
    "jobprofile.edit",
    "resource.edit",
    "report.org.view",
]
LEARNER_ROLE = "Learner"
LEARNER_CAPABILITIES = ["directory.view", "skill.claim.submit"]

# Every new organization starts with these system roles, so the first admin can
# invite people without handing out admin by default.
STARTER_ROLES: dict[str, list[str]] = {
    ADMIN_ROLE: ADMIN_CAPABILITIES,
    LEARNER_ROLE: LEARNER_CAPABILITIES,
}


class ProvisionError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@transaction.atomic
def provision_tenant(*, name: str, slug: str, admin_email: str, actor: Any) -> dict[str, Any]:
    """Create the organisation, its starter roles, and a pending admin invitation.

    The person is stored with an unusable password. They join by accepting the
    invitation (``POST /api/auth/invitations/accept/``), which sets the password
    and opens the membership and role grant.
    """
    from core import audit

    admin_email = admin_email.strip().lower()
    if Tenant.objects.filter(slug=slug).exists():
        raise ProvisionError(f"A tenant with slug '{slug}' already exists.")

    try:
        tenant = Tenant.objects.create(
            name=name.strip(),
            slug=slug,
            status="active",
            plan="pro",
        )
    except IntegrityError as exc:
        raise ProvisionError(f"A tenant with slug '{slug}' already exists.") from exc

    person_model = get_user_model()
    person = person_model.objects.filter(email=admin_email).first()
    if person is None:
        person = person_model.objects.create_user(
            email=admin_email,
            display_name=admin_email.split("@", 1)[0],
        )
        person.set_unusable_password()
        person.save(update_fields=["password"])

    for key in ADMIN_CAPABILITIES + LEARNER_CAPABILITIES:
        Capability.objects.get_or_create(key=key)

    with tenant_context(tenant.id):
        for role_name, capabilities in STARTER_ROLES.items():
            role = Role.objects.create(tenant=tenant, name=role_name, is_system=True)
            for key in capabilities:
                RoleCapability.objects.create(tenant=tenant, role=role, capability_id=key)

    invitation = create_invitation(
        email=admin_email,
        role_name=ADMIN_ROLE,
        actor=actor,
        tenant_id=tenant.id,
    )
    audit.record(
        actor=actor,
        action="tenant.provision",
        resource=tenant,
        tenant_id=tenant.id,
        admin_email=admin_email,
    )
    return {
        "tenant": {"id": str(tenant.id), "name": tenant.name, "slug": tenant.slug},
        "admin": {"id": str(person.id), "email": person.email, "display_name": person.display_name},
        "role": ADMIN_ROLE,
        "invitation": invitation,
    }
