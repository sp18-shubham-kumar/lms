"""
Email invitations.

An admin creates a pending invitation. The raw token is mailed once and only
its SHA-256 hash is stored. Accepting the token creates (or reuses) the person,
sets their password, and opens a membership plus an optional role grant.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.authz.models import Role, RoleGrant
from apps.identity.models import Invitation, Membership
from core.context import tenant_context


class InvitationError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _invite_url(raw_token: str) -> str:
    origin = settings.FRONTEND_ORIGIN.rstrip("/")
    return f"{origin}/invite/accept?token={raw_token}"


def to_payload(invitation: Invitation) -> dict[str, Any]:
    role = invitation.role
    return {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": role.name if role is not None else "",
        "status": invitation.status,
        "expires_at": invitation.expires_at.isoformat(),
    }


def _role_in_tenant(role_name: str, tenant_id: Any) -> Role | None:
    """The named role in this tenant, or None. Never a role from another tenant."""
    if not role_name:
        return None
    return Role.all_tenants.filter(tenant_id=tenant_id, name=role_name).first()


@transaction.atomic
def create_invitation(*, email: str, role_name: str, actor: Any, tenant_id: Any) -> dict[str, Any]:
    """Create a pending invitation and email the accept link. Writes the hash only."""
    from apps.identity.models import Tenant
    from core import audit

    email = email.strip().lower()
    role_name = role_name.strip()
    role = _role_in_tenant(role_name, tenant_id)
    if role_name and role is None:
        raise InvitationError(f"Unknown role: {role_name}")

    already = Invitation.objects.filter(
        email=email, status=Invitation.Status.PENDING, expires_at__gt=timezone.now()
    ).exists()
    if already:
        raise InvitationError("An invitation is already pending for this email.")

    raw_token = secrets.token_urlsafe(32)
    invitation = Invitation.objects.create(
        tenant_id=tenant_id,
        email=email,
        role=role,
        token_hash=hash_token(raw_token),
        onboarding_token_hash=hash_token(secrets.token_urlsafe(32)),
        expires_at=timezone.now() + timedelta(days=settings.INVITATION_DAYS),
        status=Invitation.Status.PENDING,
        invited_by=actor,
    )
    tenant = Tenant.objects.get(id=tenant_id)
    try:
        send_mail(
            subject=f"You're invited to {tenant.name}",
            message=(
                f"You've been invited to {tenant.name} on Skills LMS.\n\n"
                f"Set your password and join:\n{_invite_url(raw_token)}\n\n"
                f"This link expires in {settings.INVITATION_DAYS} days."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:
        raise InvitationError("Could not send the invitation email.", status_code=502) from exc

    audit.record(
        actor=actor,
        action="member.invite",
        resource=invitation,
        tenant_id=tenant_id,
        email=email,
        role=role_name,
    )
    return to_payload(invitation)


@transaction.atomic
def accept_invitation(*, raw_token: str, password: str) -> dict[str, Any]:
    """Consume a token: set the password, open the membership, grant the role."""
    from core import audit

    invitation = (
        Invitation.all_tenants.select_related("tenant")
        .filter(token_hash=hash_token(raw_token))
        .first()
    )
    if (
        invitation is None
        or invitation.status != Invitation.Status.PENDING
        or invitation.expires_at <= timezone.now()
    ):
        raise InvitationError("This invitation is invalid or has expired.")

    person_model = get_user_model()
    person = person_model.objects.filter(email=invitation.email).first()
    if person is None:
        person = person_model.objects.create_user(
            email=invitation.email,
            display_name=invitation.email.split("@", 1)[0],
        )

    try:
        validate_password(password, user=person)
    except DjangoValidationError as exc:
        raise InvitationError(" ".join(exc.messages)) from exc

    person.set_password(password)
    person.save(update_fields=["password"])

    with tenant_context(invitation.tenant_id):
        Membership.objects.get_or_create(
            person=person,
            tenant_id=invitation.tenant_id,
            defaults={"status": "active", "joined_at": timezone.now()},
        )
        if invitation.role_id:
            role = Role.objects.filter(pk=invitation.role_id).first()
            if role is None:
                raise InvitationError("The invited role is no longer available.")
            RoleGrant.objects.get_or_create(
                tenant_id=invitation.tenant_id,
                principal_type="person",
                principal_id=person.id,
                role=role,
            )

    invitation.status = Invitation.Status.ACCEPTED
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["status", "accepted_at", "updated_at"])

    audit.record(
        actor=person,
        action="member.invite.accept",
        resource=invitation,
        tenant_id=invitation.tenant_id,
        email=invitation.email,
    )
    return {"email": invitation.email, "tenant_id": str(invitation.tenant_id)}
