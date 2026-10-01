"""
Identity & tenancy models (Phase 1).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-1.md):
- Tenant        — the organisation boundary (slug, name, status, plan, theming).
- Person        — global identity, not owned by a tenant (email UNIQUE).
- OrgUnit       — tenant org hierarchy (materialised path for subtree scope).
- Membership    — links a Person to a Tenant (role, org unit, grade); one per pair.
- Invitation   — a pending email invite; only the token hash is stored.
- IdentityProvider — per-tenant OIDC config.

Conventions:
- `Tenant` and `Person` are NOT tenant-scoped (they define/cross the boundary),
  so they inherit `core.models.UUIDModel` + `TimeStampedModel` directly.
- Every other model here inherits `core.models.TenantScopedModel`.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import TenantScopedModel, TimeStampedModel, UUIDModel


class PersonManager(BaseUserManager["Person"]):
    """Manager for the custom Person user (email is the identifier)."""

    use_in_migrations = True

    def create_user(
        self, email: str, display_name: str, password: str | None = None, **extra: object
    ) -> Person:
        if not email:
            raise ValueError("Person requires an email.")
        email = self.normalize_email(email)
        person = Person(email=email, display_name=display_name, **extra)
        person.set_password(password)
        person.save(using=self._db)
        return person

    def create_superuser(
        self, email: str, display_name: str, password: str | None = None, **extra: object
    ) -> Person:
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        return self.create_user(email, display_name, password, **extra)


class Person(AbstractBaseUser, PermissionsMixin, UUIDModel, TimeStampedModel):
    """Global identity. NOT tenant-scoped — a person crosses tenants."""

    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=255)
    did = models.CharField(max_length=255, blank=True, default="")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = PersonManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["display_name"]

    def __str__(self) -> str:
        return self.email


class Tenant(UUIDModel, TimeStampedModel):
    """The organisation boundary. NOT tenant-scoped — it defines the boundary."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="active")
    plan = models.CharField(max_length=32, default="free")
    accent_color = models.CharField(max_length=9, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")
    description = models.TextField(blank=True, default="")

    def __str__(self) -> str:
        return self.name


class OrgUnit(TenantScopedModel):
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="children"
    )
    name = models.CharField(max_length=255)
    path = models.CharField(max_length=1024, blank=True, default="")

    def __str__(self) -> str:
        return self.name


class Membership(TenantScopedModel):
    person = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="memberships"
    )
    org_unit = models.ForeignKey(
        OrgUnit, null=True, blank=True, on_delete=models.SET_NULL, related_name="members"
    )
    employee_ref = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=32, default="active")
    joined_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["person", "tenant"], name="uniq_membership_person_tenant"
            )
        ]


class Invitation(TenantScopedModel):
    """A pending email invite. The raw token is mailed once; only its hash is stored."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        CANCELLED = "cancelled", "Cancelled"

    email = models.EmailField()
    role = models.ForeignKey(
        "authz.Role",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invitations",
    )
    token_hash = models.CharField(max_length=64, unique=True)
    # Present on the existing table. Accept uses token_hash; this stays empty until used.
    onboarding_token_hash = models.CharField(max_length=64, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_invitations",
    )

    def __str__(self) -> str:
        return f"{self.email} ({self.status})"

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "email"],
                condition=models.Q(status="pending"),
                name="uniq_pending_invitation_tenant_email",
            ),
            models.UniqueConstraint(
                fields=["onboarding_token_hash"],
                condition=~models.Q(onboarding_token_hash=""),
                name="uniq_invitation_onboarding_token_hash",
            ),
        ]


class IdentityProvider(TenantScopedModel):
    kind = models.CharField(max_length=32)
    issuer = models.CharField(max_length=255, blank=True, default="")
    client_id = models.CharField(max_length=255, blank=True, default="")
    domain_hint = models.CharField(max_length=255, blank=True, default="")
