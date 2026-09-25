"""
Identity & tenancy models (Phase 1).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-1.md):
- Tenant        — the organisation boundary (slug, name, status, plan, theming).
- Person        — global identity, not owned by a tenant (email UNIQUE).
- OrgUnit       — tenant org hierarchy (materialised path for subtree scope).
- Membership    — links a Person to a Tenant (role, org unit, grade); one per pair.
- IdentityProvider — per-tenant OIDC config.

Conventions:
- `Tenant` and `Person` are NOT tenant-scoped (they define/cross the boundary),
  so they inherit `core.models.UUIDModel` + `TimeStampedModel` directly.
- Every other model here inherits `core.models.TenantScopedModel`.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import TimeStampedModel, UUIDModel


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
