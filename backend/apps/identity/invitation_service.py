"""
Email invitations.

An admin creates a pending invitation. The raw token is mailed once and only
its SHA-256 hash is stored. Accepting the token sets the password, and opens
a membership plus the invited role grant.

Platform provisioning, member invite, and CSV import all call
:func:`create_invitation`, so every email uses the same accept link.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta
from typing import Any
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.authz.models import Role, RoleGrant
from apps.identity.models import Invitation, Membership, Tenant
from core.context import tenant_context


class InvitationError(Exception):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def invite_url(raw_token: str) -> str:
    origin = settings.FRONTEND_ORIGIN.rstrip("/")
    return f"{origin}/invite/accept?token={raw_token}"


def to_payload(invitation: Invitation, *, token: str | None = None) -> dict[str, Any]:
    role = invitation.role
    payload: dict[str, Any] = {
        "id": str(invitation.id),
        "email": invitation.email,
        "role": role.name if role is not None else "",
        "role_id": str(invitation.role_id) if invitation.role_id else None,
        "status": invitation.status,
        "expires_at": invitation.expires_at.isoformat(),
    }
    if token is not None:
        payload["token"] = token
    return payload


def _role_in_tenant(role_name: str, tenant_id: Any) -> Role | None:
    """The named role in this tenant, or None. Never a role from another tenant."""
    if not role_name:
        return None
    return Role.all_tenants.filter(tenant_id=tenant_id, name=role_name).first()


def resolve_role(*, role_ref: str, tenant_id: Any) -> Role:
    """Resolve a role name or id. Reject a role that belongs to another tenant."""
    role_ref = role_ref.strip()
    role: Role | None
    try:
        role_id = UUID(role_ref)
    except ValueError:
        role = _role_in_tenant(role_ref, tenant_id)
        if role is None:
            raise InvitationError(f"Unknown role: {role_ref}") from None
        return role

    role = Role.all_tenants.filter(pk=role_id).first()
    if role is None or role.tenant_id != tenant_id:
        raise InvitationError("The role does not belong to this tenant.")
    return role


def _send_invite(invitation: Invitation, raw_token: str) -> None:
    tenant = Tenant.objects.get(id=invitation.tenant_id)
    try:
        send_mail(
            subject=f"You're invited to {tenant.name}",
            message=(
                f"You've been invited to {tenant.name} on Skills LMS.\n\n"
                f"Set your password and join:\n{invite_url(raw_token)}\n\n"
                f"This link expires in {settings.INVITATION_DAYS} days."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            fail_silently=False,
        )
    except Exception as exc:
        raise InvitationError("Could not send the invitation email.", status_code=502) from exc


def _new_token(invitation: Invitation) -> str:
    raw_token = secrets.token_urlsafe(32)
    invitation.token_hash = hash_token(raw_token)
    invitation.onboarding_token_hash = ""
    invitation.expires_at = timezone.now() + timedelta(days=settings.INVITATION_DAYS)
    invitation.save(
        update_fields=["token_hash", "onboarding_token_hash", "expires_at", "updated_at"]
    )
    return raw_token


def _pending(invitation_id: Any, tenant_id: Any) -> Invitation:
    invitation = (
        Invitation.all_tenants.select_related("role")
        .filter(id=invitation_id, tenant_id=tenant_id)
        .first()
    )
    if invitation is None:
        raise InvitationError("Invitation not found.", status_code=404)
    if invitation.status != Invitation.Status.PENDING:
        raise InvitationError("Only a pending invitation can be changed.")
    return invitation


@transaction.atomic
def create_invitation(
    *, email: str, role_name: str, actor: Any, tenant_id: Any, role: Role | None = None
) -> dict[str, Any]:
    """Create a pending invitation and email the accept link. Writes the hash only."""
    from core import audit

    email = email.strip().lower()
    if role is None:
        role = _role_in_tenant(role_name, tenant_id)
    if role is None or role.tenant_id != tenant_id:
        raise InvitationError(f"Unknown role: {role_name or role}")

    with tenant_context(tenant_id):
        already = Invitation.objects.filter(
            email=email,
            status=Invitation.Status.PENDING,
        ).exists()
        if already:
            raise InvitationError("An invitation is already pending for this email.")

        raw_token = secrets.token_urlsafe(32)
        invitation = Invitation.objects.create(
            tenant_id=tenant_id,
            email=email,
            role=role,
            token_hash=hash_token(raw_token),
            onboarding_token_hash="",
            expires_at=timezone.now() + timedelta(days=settings.INVITATION_DAYS),
            status=Invitation.Status.PENDING,
            invited_by=actor,
        )

    _send_invite(invitation, raw_token)
    audit.record(
        actor=actor,
        action="member.invite",
        resource=invitation,
        tenant_id=tenant_id,
        email=email,
        role=role.name,
    )
    return to_payload(invitation, token=raw_token)


@transaction.atomic
def resend_invitation(*, invitation_id: Any, actor: Any, tenant_id: Any) -> dict[str, Any]:
    """Replace the token and expiry, then email the new accept link."""
    from core import audit

    invitation = _pending(invitation_id, tenant_id)
    raw_token = _new_token(invitation)
    _send_invite(invitation, raw_token)
    audit.record(
        actor=actor,
        action="member.invite.resend",
        resource=invitation,
        tenant_id=tenant_id,
        email=invitation.email,
    )
    return to_payload(invitation, token=raw_token)


@transaction.atomic
def cancel_invitation(*, invitation_id: Any, actor: Any, tenant_id: Any) -> None:
    """Mark a pending invitation cancelled so the email can be invited again."""
    from core import audit

    invitation = _pending(invitation_id, tenant_id)
    invitation.status = Invitation.Status.CANCELLED
    invitation.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=actor,
        action="member.invite.cancel",
        resource=invitation,
        tenant_id=tenant_id,
        email=invitation.email,
    )


def _role_for_accept(invitation: Invitation) -> Role | None:
    """The invitation's role, or None when no role was stored.

    A stored role id must still exist and belong to the invitation's tenant.
    """
    if invitation.role_id is None:
        return None
    role = Role.all_tenants.filter(pk=invitation.role_id).first()
    if role is None or role.tenant_id != invitation.tenant_id:
        raise InvitationError("The invited role does not belong to this tenant.")
    return role


@transaction.atomic
def accept_invitation(*, raw_token: str, password: str) -> dict[str, Any]:
    """Consume a token: set the password, open the membership, grant the role."""
    from core import audit

    invitation = (
        Invitation.all_tenants.select_related("tenant", "role")
        .filter(token_hash=hash_token(raw_token))
        .first()
    )
    if (
        invitation is None
        or invitation.status != Invitation.Status.PENDING
        or invitation.expires_at <= timezone.now()
    ):
        raise InvitationError("This invitation is invalid or has expired.")

    role = _role_for_accept(invitation)

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
        if role is not None:
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
