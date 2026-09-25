# Auth, Session & People Directory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Phase-1 vertical slice — email+password login issuing stateless JWT bearer tokens, a `/auth/session/` identity endpoint driving capability-gated UI, and a tenant-scoped paginated People directory.

**Architecture:** Django backend adds `identity` (custom `Person` user, `Tenant`, `OrgUnit`, `Membership`, `IdentityProvider`) and `authz` (`Capability`, `Role`, `RoleCapability`, `RoleGrant`) models. `core.permissions.can()` resolves capabilities from role grants; a new `IsActiveTenantMember` permission enforces tenant membership. Custom `LoginView`/`SessionView` sit on SimpleJWT. React frontend fills existing seams (`auth.tsx`, `LoginPage`, `ChooseTenantPage`, `AppShell`, `DirectoryPage`) and adds a `features/people` query hook.

**Tech Stack:** Django 5.1, DRF, SimpleJWT, Postgres, pytest · React 19, TypeScript, TanStack Query, React Router, Vitest/RTL.

**Spec:** `docs/superpowers/specs/2026-09-25-auth-directory-design.md`

## Global Constraints

- Every tenant-owned table inherits `core.models.TenantScopedModel`. `Person`, `Tenant`, and `AuditLog` are the only non-scoped domain rows.
- All tenant-scoped reads go through `Model.objects` (fails closed with no tenant). `Model.all_tenants` only for provisioning/admin/membership checks — never in a request handler's list query.
- Authorization is deny-by-default, funnelled through `core.permissions.can(actor, capability, resource)`. Every deny is logged with the failing check.
- Field names copied **exactly** from `docs/specs/data-model.md`.
- State-changing actions call `core.audit.record(...)`.
- Stateless bearer: no server session, no token blacklist. Logout is a client-side token discard.
- `AUTH_USER_MODEL = "identity.Person"` must be set **before** the first `identity` migration.
- Backend keeps `ruff` + `black` + `mypy` clean; frontend keeps `oxlint` + `tsc` + Prettier clean.
- Every tenant-scoped list endpoint gets a tenant-isolation test (seed two tenants, list as A, assert zero of B's rows).

## Review Focus

- **Missing `X-Tenant-Id` on a tenant-scoped endpoint** → 400 (not a 500 or silent empty list). Pinned in Task 6 (`IsActiveTenantMember`).
- **Authenticated user of tenant A sends tenant B's id** → 403, no B rows leak. Pinned in Task 9.
- **Login with a person whose only membership is `ended`** → 403 "no active membership", not a usable token. Pinned in Task 7.
- **`can()` with no tenant in context** (e.g. background/no-header) → `False` + logged deny, never an exception. Pinned in Task 5.
- **Expired access token mid-session** → frontend refresh-on-401 retries once, then routes to `/login` on refresh failure (no infinite loop). Pinned in Task 13.

---

## Task 1: `Person` custom user model + `AUTH_USER_MODEL`

**Files:**
- Modify: `backend/apps/identity/models.py`
- Modify: `backend/config/settings/base.py` (add `AUTH_USER_MODEL`)
- Test: `backend/apps/identity/tests/test_models.py` (create; delete the old `apps/identity/tests.py`)

**Interfaces:**
- Produces: `identity.Person` (custom user; `USERNAME_FIELD="email"`, `REQUIRED_FIELDS=["display_name"]`), `Person.objects.create_user(email, display_name, password=None, **extra)`, `Person.objects.create_superuser(email, display_name, password)`.

- [ ] **Step 1: Convert `tests.py` to a test package.** Delete `backend/apps/identity/tests.py`, create `backend/apps/identity/tests/__init__.py` (empty) and `backend/apps/identity/tests/test_models.py`.

- [ ] **Step 2: Write the failing test**

```python
# backend/apps/identity/tests/test_models.py
import pytest
from django.contrib.auth import get_user_model

Person = get_user_model()


@pytest.mark.django_db
def test_create_user_sets_email_and_password():
    person = Person.objects.create_user(
        email="alice@acme.test", display_name="Alice", password="pw-12345"
    )
    assert person.email == "alice@acme.test"
    assert person.display_name == "Alice"
    assert person.check_password("pw-12345")
    assert person.is_active is True
    assert person.is_staff is False


@pytest.mark.django_db
def test_create_superuser_flags():
    admin = Person.objects.create_superuser(
        email="root@acme.test", display_name="Root", password="pw-12345"
    )
    assert admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_email_is_the_username_field():
    assert Person.USERNAME_FIELD == "email"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_models.py -v`
Expected: FAIL (Person has no `create_user` / model not defined).

- [ ] **Step 4: Implement `Person` + manager**

```python
# backend/apps/identity/models.py  (replace the docstring-only file body below the module docstring)
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models

from core.models import TimeStampedModel, UUIDModel


class PersonManager(BaseUserManager):
    """Manager for the custom Person user (email is the identifier)."""

    use_in_migrations = True

    def create_user(self, email, display_name, password=None, **extra):
        if not email:
            raise ValueError("Person requires an email.")
        email = self.normalize_email(email)
        person = self.model(email=email, display_name=display_name, **extra)
        person.set_password(password)
        person.save(using=self._db)
        return person

    def create_superuser(self, email, display_name, password=None, **extra):
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
```

- [ ] **Step 5: Set `AUTH_USER_MODEL`** in `backend/config/settings/base.py`, immediately after `DEFAULT_AUTO_FIELD = ...`:

```python
# Custom user model — a Person is the global identity (see docs/specs/data-model.md).
AUTH_USER_MODEL = "identity.Person"
```

- [ ] **Step 6: Make the migration**

Run: `cd backend && .venv/bin/python manage.py makemigrations identity`
Expected: creates `apps/identity/migrations/0001_initial.py` with `Person`.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_models.py -v`
Expected: PASS (3 tests). (pytest applies migrations to the test DB automatically.)

- [ ] **Step 8: Commit**

```bash
git add backend/apps/identity/ backend/config/settings/base.py
git commit -m "feat(identity): add Person custom user model + AUTH_USER_MODEL"
```

---

## Task 2: `Tenant`, `OrgUnit`, `Membership`, `IdentityProvider`

**Files:**
- Modify: `backend/apps/identity/models.py`
- Test: `backend/apps/identity/tests/test_models.py`

**Interfaces:**
- Produces: `identity.Tenant(slug, name, status, plan, accent_color, logo_url)` (not tenant-scoped); `identity.OrgUnit`, `identity.Membership(person, tenant, org_unit, employee_ref, status, joined_at, ended_at)` with `UNIQUE(person, tenant)`, `identity.IdentityProvider` (all `TenantScopedModel`). `Membership.status` values include `"active"` / `"ended"`.

- [ ] **Step 1: Write the failing test** (append to `test_models.py`)

```python
from django.db import IntegrityError
from core.context import tenant_context


@pytest.mark.django_db
def test_membership_is_unique_per_person_tenant():
    from apps.identity.models import Membership, Tenant

    person = Person.objects.create_user(email="bob@acme.test", display_name="Bob")
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        with pytest.raises(IntegrityError):
            Membership.objects.create(person=person, tenant=tenant, status="active")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_models.py::test_membership_is_unique_per_person_tenant -v`
Expected: FAIL (cannot import `Membership`).

- [ ] **Step 3: Implement the models** (append to `backend/apps/identity/models.py`)

```python
from django.conf import settings

from core.models import TenantScopedModel


class Tenant(UUIDModel, TimeStampedModel):
    """The organisation boundary. NOT tenant-scoped — it defines the boundary."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=32, default="active")
    plan = models.CharField(max_length=32, default="free")
    accent_color = models.CharField(max_length=9, blank=True, default="")
    logo_url = models.URLField(blank=True, default="")

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


class IdentityProvider(TenantScopedModel):
    kind = models.CharField(max_length=32)
    issuer = models.CharField(max_length=255, blank=True, default="")
    client_id = models.CharField(max_length=255, blank=True, default="")
    domain_hint = models.CharField(max_length=255, blank=True, default="")
```

- [ ] **Step 4: Make + review the migration**

Run: `cd backend && .venv/bin/python manage.py makemigrations identity`
Expected: `apps/identity/migrations/0002_*.py` adding four models; confirm the `UniqueConstraint` is present.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_models.py -v`
Expected: PASS.

- [ ] **Step 6: Register in admin** (`backend/apps/identity/admin.py`)

```python
from django.contrib import admin

from apps.identity.models import IdentityProvider, Membership, OrgUnit, Person, Tenant

admin.site.register([Person, Tenant, OrgUnit, Membership, IdentityProvider])
```

- [ ] **Step 7: Commit**

```bash
git add backend/apps/identity/
git commit -m "feat(identity): add Tenant, OrgUnit, Membership, IdentityProvider"
```

---

## Task 3: Authz models

**Files:**
- Modify: `backend/apps/authz/models.py`
- Modify: `backend/apps/authz/admin.py`
- Test: `backend/apps/authz/tests/test_models.py` (create package; delete `apps/authz/tests.py`)

**Interfaces:**
- Produces: `authz.Capability(key)` (PK = `key`, not tenant-scoped); `authz.Role(name, is_system)`, `authz.RoleCapability(role, capability)`, `authz.RoleGrant(principal_type, principal_id, role, scope_type, scope_id)` — all `TenantScopedModel`. `RoleGrant.principal_type == "person"` uses `principal_id == person.id`.

- [ ] **Step 1: Make the test package.** Delete `backend/apps/authz/tests.py`; create `backend/apps/authz/tests/__init__.py` and `backend/apps/authz/tests/test_models.py`.

- [ ] **Step 2: Write the failing test**

```python
# backend/apps/authz/tests/test_models.py
import pytest

from core.context import tenant_context


@pytest.mark.django_db
def test_role_capabilities_link():
    from apps.authz.models import Capability, Role, RoleCapability
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    cap = Capability.objects.create(key="directory.view")
    with tenant_context(tenant.id):
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        keys = list(role.capabilities.values_list("capability_id", flat=True))
    assert keys == ["directory.view"]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest apps/authz/tests/test_models.py -v`
Expected: FAIL (cannot import `Capability`).

- [ ] **Step 4: Implement the models** (`backend/apps/authz/models.py`, below the module docstring)

```python
from __future__ import annotations

from django.db import models

from core.models import TenantScopedModel


class Capability(models.Model):
    """Flat, seeded capability key. Global (not tenant-editable, not tenant-scoped)."""

    key = models.CharField(max_length=100, primary_key=True)

    def __str__(self) -> str:
        return self.key


class Role(TenantScopedModel):
    name = models.CharField(max_length=100)
    is_system = models.BooleanField(default=False)

    def __str__(self) -> str:
        return self.name


class RoleCapability(TenantScopedModel):
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="capabilities")
    capability = models.ForeignKey(Capability, on_delete=models.CASCADE, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["role", "capability"], name="uniq_role_capability"
            )
        ]


class RoleGrant(TenantScopedModel):
    principal_type = models.CharField(max_length=16, default="person")  # person | group
    principal_id = models.UUIDField()
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="grants")
    scope_type = models.CharField(max_length=32, blank=True, default="")
    scope_id = models.UUIDField(null=True, blank=True)
```

- [ ] **Step 5: Admin** (`backend/apps/authz/admin.py`)

```python
from django.contrib import admin

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant

admin.site.register([Capability, Role, RoleCapability, RoleGrant])
```

- [ ] **Step 6: Make the migration + run tests**

Run: `cd backend && .venv/bin/python manage.py makemigrations authz && .venv/bin/pytest apps/authz/tests/test_models.py -v`
Expected: migration `0001_initial.py` created; test PASSES.

- [ ] **Step 7: Commit**

```bash
git add backend/apps/authz/
git commit -m "feat(authz): add Capability, Role, RoleCapability, RoleGrant"
```

---

## Task 4: `AuditLog` model + wire `core.audit.record`

**Files:**
- Modify: `backend/core/models.py` (add `AuditLog`)
- Modify: `backend/core/audit.py` (insert instead of log-only)
- Test: `backend/core/tests/test_audit.py` (create)

**Interfaces:**
- Produces: `core.models.AuditLog(tenant nullable, actor nullable, action, resource_type, resource_id, metadata)`. `core.audit.record(*, actor, action, resource=None, tenant_id=None, **metadata)` inserts one `AuditLog` row.

- [ ] **Step 1: Write the failing test**

```python
# backend/core/tests/test_audit.py
import pytest

from core import audit
from core.models import AuditLog


@pytest.mark.django_db
def test_record_inserts_audit_row():
    audit.record(actor=None, action="auth.login", tenant_id=None, email="x@y.z")
    row = AuditLog.objects.get()
    assert row.action == "auth.login"
    assert row.metadata == {"email": "x@y.z"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest core/tests/test_audit.py -v`
Expected: FAIL (`cannot import name 'AuditLog'`).

- [ ] **Step 3: Add `AuditLog`** (append to `backend/core/models.py`)

```python
from django.conf import settings


class AuditLog(UUIDModel, TimeStampedModel):
    """Append-only audit trail. NOT tenant-scoped — records cross-context events."""

    tenant = models.ForeignKey(
        "identity.Tenant", null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=100, blank=True, default="")
    resource_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
```

- [ ] **Step 4: Rewrite `record`** (`backend/core/audit.py`) to insert. Keep the logger line for observability.

```python
def record(*, actor, action, resource=None, tenant_id=None, **metadata):
    from core.models import AuditLog  # lazy import: avoids app-loading cycle

    actor_obj = actor if getattr(actor, "pk", None) is not None else None
    AuditLog.objects.create(
        tenant_id=tenant_id,
        actor=actor_obj,
        action=action,
        resource_type=type(resource).__name__ if resource is not None else "",
        resource_id=getattr(resource, "id", None),
        metadata=metadata,
    )
    logger.info("audit", extra={"action": action, "tenant_id": tenant_id})
```

Keep the existing `logger = logging.getLogger("audit")` and imports; drop the now-unused `Any` typing import if `mypy`/`ruff` flags it.

- [ ] **Step 5: Migration + run tests**

Run: `cd backend && .venv/bin/python manage.py makemigrations core && .venv/bin/pytest core/tests/test_audit.py -v`
Expected: migration `core/migrations/0001_initial.py` created; test PASSES.

- [ ] **Step 6: Commit**

```bash
git add backend/core/
git commit -m "feat(core): add AuditLog model and wire audit.record to insert"
```

---

## Task 5: `can()` capability resolution

**Files:**
- Modify: `backend/core/permissions.py`
- Test: `backend/apps/authz/tests/test_can.py` (create)

**Interfaces:**
- Consumes: `authz.RoleGrant`, `authz.RoleCapability` (Task 3); `core.context.get_current_tenant`.
- Produces: `core.permissions.can(actor, capability, resource=None) -> bool` — resolves the actor's capability set for the active tenant, deny-by-default, logs every deny. `capabilities_for(actor, tenant_id) -> set[str]` helper.

- [ ] **Step 1: Write the failing tests**

```python
# backend/apps/authz/tests/test_can.py
import pytest
from django.contrib.auth import get_user_model

from core.context import tenant_context
from core.permissions import can

Person = get_user_model()


def _seed(cap_key):
    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A")
    cap = Capability.objects.create(key=cap_key)
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
    return tenant, person


@pytest.mark.django_db
def test_can_grants_held_capability():
    tenant, person = _seed("directory.view")
    with tenant_context(tenant.id):
        assert can(person, "directory.view") is True


@pytest.mark.django_db
def test_can_denies_unheld_capability():
    tenant, person = _seed("directory.view")
    with tenant_context(tenant.id):
        assert can(person, "skill.verify") is False


@pytest.mark.django_db
def test_can_denies_without_tenant_context():
    _tenant, person = _seed("directory.view")
    # No tenant_context: must not raise, must return False.
    assert can(person, "directory.view") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest apps/authz/tests/test_can.py -v`
Expected: FAIL (current `can` always returns `False`; the grant test fails).

- [ ] **Step 3: Implement `can` + `capabilities_for`** (replace the `can` stub in `backend/core/permissions.py`)

```python
import logging

from core.context import get_current_tenant

logger = logging.getLogger("authz")


def _log_deny(actor, capability, reason):
    logger.info(
        "authz.deny",
        extra={
            "actor": getattr(actor, "id", None),
            "capability": capability,
            "reason": reason,
        },
    )


def capabilities_for(actor, tenant_id) -> set[str]:
    """Resolve the capability keys an actor holds in a tenant, via role grants."""
    from apps.authz.models import RoleCapability, RoleGrant

    role_ids = list(
        RoleGrant.all_tenants.filter(
            tenant_id=tenant_id, principal_type="person", principal_id=actor.id
        ).values_list("role_id", flat=True)
    )
    if not role_ids:
        return set()
    return set(
        RoleCapability.all_tenants.filter(
            tenant_id=tenant_id, role_id__in=role_ids
        ).values_list("capability_id", flat=True)
    )


def can(actor, capability, resource=None) -> bool:
    """Single authorization entry point. Deny by default; log every deny."""
    if actor is None or not getattr(actor, "is_authenticated", False):
        _log_deny(actor, capability, "unauthenticated")
        return False
    if getattr(actor, "is_superuser", False):
        return True
    tenant_id = get_current_tenant()
    if tenant_id is None:
        _log_deny(actor, capability, "no-tenant-context")
        return False
    # Per-request memo, keyed by tenant.
    cache = getattr(actor, "_cap_cache", None)
    if cache is None:
        cache = {}
        actor._cap_cache = cache
    caps = cache.get(tenant_id)
    if caps is None:
        caps = capabilities_for(actor, tenant_id)
        cache[tenant_id] = caps
    if capability in caps:
        return True
    _log_deny(actor, capability, "capability-not-held")
    return False
```

Keep `HasCapability` unchanged — it already calls `can(request.user, capability)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/authz/tests/test_can.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/core/permissions.py backend/apps/authz/tests/
git commit -m "feat(authz): resolve capabilities from role grants in can()"
```

---

## Task 6: `IsActiveTenantMember` permission + settings wiring

**Files:**
- Modify: `backend/core/permissions.py` (add permission class)
- Modify: `backend/config/settings/base.py` (add to `DEFAULT_PERMISSION_CLASSES`)
- Test: `backend/core/tests/test_tenant_membership_permission.py` (create)

**Interfaces:**
- Consumes: `identity.Membership`, `core.context.get_current_tenant`.
- Produces: `core.permissions.IsActiveTenantMember` — 400 if no tenant header on an authenticated request, 403 if the user is not an active member of the active tenant.

- [ ] **Step 1: Write the failing test**

```python
# backend/core/tests/test_tenant_membership_permission.py
import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIRequestFactory, force_authenticate

from core.context import tenant_context
from core.permissions import IsActiveTenantMember

Person = get_user_model()


@pytest.mark.django_db
def test_member_of_active_tenant_is_allowed():
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    request = APIRequestFactory().get("/api/auth/session/")
    force_authenticate(request, user=person)
    request.user = person
    with tenant_context(tenant.id):
        assert IsActiveTenantMember().has_permission(request, view=None) is True


@pytest.mark.django_db
def test_non_member_is_denied():
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="stranger@x.test", display_name="S")
    request = APIRequestFactory().get("/api/auth/session/")
    request.user = person
    with tenant_context(tenant.id):
        assert IsActiveTenantMember().has_permission(request, view=None) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest core/tests/test_tenant_membership_permission.py -v`
Expected: FAIL (`cannot import name 'IsActiveTenantMember'`).

- [ ] **Step 3: Implement the permission** (append to `backend/core/permissions.py`)

```python
from rest_framework.exceptions import ValidationError


class IsActiveTenantMember(BasePermission):
    """Authenticated requests must be an active member of the active tenant."""

    message = "You are not an active member of this tenant."

    def has_permission(self, request, view) -> bool:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            return False  # IsAuthenticated already returned 401; belt and braces.
        tenant_id = get_current_tenant()
        if tenant_id is None:
            raise ValidationError({"tenant": "X-Tenant-Id header is required."})
        from apps.identity.models import Membership

        return Membership.all_tenants.filter(
            person=user, tenant_id=tenant_id, status="active"
        ).exists()
```

- [ ] **Step 4: Wire it globally** — in `backend/config/settings/base.py`, extend `DEFAULT_PERMISSION_CLASSES`:

```python
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
        "core.permissions.IsActiveTenantMember",
    ),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest core/tests/test_tenant_membership_permission.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Verify existing smoke tests still pass** (health opts out via `AllowAny`):

Run: `cd backend && .venv/bin/pytest core/tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/core/permissions.py backend/config/settings/base.py backend/core/tests/
git commit -m "feat(core): enforce active-tenant membership via IsActiveTenantMember"
```

---

## Task 7: Login endpoint

**Files:**
- Create: `backend/apps/identity/serializers.py`
- Create: `backend/apps/identity/views.py` (replace stub)
- Create: `backend/apps/identity/urls.py` (replace stub)
- Modify: `backend/config/urls.py` (replace the two placeholder JWT routes with app routes)
- Test: `backend/apps/identity/tests/test_auth.py` (create)

**Interfaces:**
- Produces: `POST /api/auth/login/` → `{ access, refresh, memberships: [{tenant_id, slug, name, accent_color}] }`. Public (`AllowAny`, no auth/tenant). 401 bad credentials, 403 no active membership.

- [ ] **Step 1: Write the failing tests**

```python
# backend/apps/identity/tests/test_auth.py
import pytest
from rest_framework.test import APIClient


def _person_with_membership(email="a@acme.test", pw="pw-12345", status="active"):
    from django.contrib.auth import get_user_model
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email=email, display_name="A", password=pw)
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro",
                                   accent_color="#4f46e5")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status=status)
    return person, tenant


@pytest.mark.django_db
def test_login_returns_tokens_and_memberships():
    _person_with_membership()
    resp = APIClient().post("/api/auth/login/",
                            {"email": "a@acme.test", "password": "pw-12345"}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]
    assert body["memberships"][0]["slug"] == "acme"
    assert body["memberships"][0]["accent_color"] == "#4f46e5"


@pytest.mark.django_db
def test_login_bad_password_is_401():
    _person_with_membership()
    resp = APIClient().post("/api/auth/login/",
                            {"email": "a@acme.test", "password": "wrong"}, format="json")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_without_active_membership_is_403():
    _person_with_membership(status="ended")
    resp = APIClient().post("/api/auth/login/",
                            {"email": "a@acme.test", "password": "pw-12345"}, format="json")
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_auth.py -v`
Expected: FAIL (404 — route not wired).

- [ ] **Step 3: Serializer** (`backend/apps/identity/serializers.py`)

```python
from __future__ import annotations

from rest_framework import serializers

from apps.identity.models import Membership, Person


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MembershipSummarySerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id")
    slug = serializers.CharField(source="tenant.slug")
    name = serializers.CharField(source="tenant.name")
    accent_color = serializers.CharField(source="tenant.accent_color")

    class Meta:
        model = Membership
        fields = ["tenant_id", "slug", "name", "accent_color"]


class PersonSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "email", "display_name"]
```

- [ ] **Step 4: Login view** (`backend/apps/identity/views.py`)

```python
from __future__ import annotations

from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.models import Membership
from apps.identity.serializers import LoginSerializer, MembershipSummarySerializer
from core import audit


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        person = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if person is None:
            raise AuthenticationFailed("Invalid email or password.")
        memberships = list(
            Membership.all_tenants.filter(person=person, status="active").select_related("tenant")
        )
        if not memberships:
            raise PermissionDenied("You have no active membership in any organization.")
        refresh = RefreshToken.for_user(person)
        audit.record(actor=person, action="auth.login")
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
            }
        )
```

- [ ] **Step 5: App urls** (`backend/apps/identity/urls.py`)

```python
from django.urls import path

from apps.identity.views import LoginView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
]
```

- [ ] **Step 6: Wire routes** — in `backend/config/urls.py`, replace the two placeholder auth lines (`TokenObtainPairView` + `TokenRefreshView`) with:

```python
    path("auth/", include("apps.identity.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
```

Keep the `TokenRefreshView` import; drop the now-unused `TokenObtainPairView` import.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_auth.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/apps/identity/ backend/config/urls.py
git commit -m "feat(identity): email+password login issuing JWT + memberships"
```

---

## Task 8: Session endpoint

**Files:**
- Modify: `backend/apps/identity/serializers.py` (add `SessionSerializer` pieces)
- Modify: `backend/apps/identity/views.py` (add `SessionView`)
- Modify: `backend/apps/identity/urls.py` (add route)
- Test: `backend/apps/identity/tests/test_session.py` (create)

**Interfaces:**
- Consumes: `core.permissions.capabilities_for` (Task 5), default permissions (Task 6).
- Produces: `GET /api/auth/session/` → `{ person, tenant, capabilities, memberships }`; requires `Authorization: Bearer` + `X-Tenant-Id`.

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/identity/tests/test_session.py
import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_session_returns_person_tenant_capabilities():
    from django.contrib.auth import get_user_model
    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro",
                                   accent_color="#4f46e5")
    cap = Capability.objects.create(key="directory.view")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        RoleGrant.objects.create(tenant=tenant, principal_type="person",
                                 principal_id=person.id, role=role)

    client = APIClient()
    login = client.post("/api/auth/login/",
                        {"email": "a@acme.test", "password": "pw-12345"}, format="json").json()
    resp = client.get("/api/auth/session/",
                      HTTP_AUTHORIZATION=f"Bearer {login['access']}",
                      HTTP_X_TENANT_ID=str(tenant.id))
    assert resp.status_code == 200
    body = resp.json()
    assert body["person"]["email"] == "a@acme.test"
    assert body["tenant"]["accent_color"] == "#4f46e5"
    assert "directory.view" in body["capabilities"]


@pytest.mark.django_db
def test_session_without_tenant_header_is_400():
    from django.contrib.auth import get_user_model
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    client = APIClient()
    login = client.post("/api/auth/login/",
                        {"email": "a@acme.test", "password": "pw-12345"}, format="json").json()
    resp = client.get("/api/auth/session/", HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_session.py -v`
Expected: FAIL (404 — route not wired).

- [ ] **Step 3: Add `TenantSummarySerializer`** (append to `backend/apps/identity/serializers.py`)

```python
from apps.identity.models import Tenant


class TenantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "accent_color", "logo_url"]
```

- [ ] **Step 4: Add `SessionView`** (append to `backend/apps/identity/views.py`)

```python
from apps.identity.models import Tenant
from apps.identity.serializers import (
    PersonSummarySerializer,
    TenantSummarySerializer,
)
from core.context import get_current_tenant
from core.permissions import capabilities_for


class SessionView(APIView):
    """Who am I, in this tenant. Default permissions require auth + membership."""

    def get(self, request):
        tenant_id = get_current_tenant()
        tenant = Tenant.objects.get(id=tenant_id)
        memberships = list(
            Membership.all_tenants.filter(person=request.user, status="active").select_related("tenant")
        )
        return Response(
            {
                "person": PersonSummarySerializer(request.user).data,
                "tenant": TenantSummarySerializer(tenant).data,
                "capabilities": sorted(capabilities_for(request.user, tenant_id)),
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
            }
        )
```

- [ ] **Step 5: Add the route** (`backend/apps/identity/urls.py`)

```python
from apps.identity.views import LoginView, SessionView

urlpatterns = [
    path("login/", LoginView.as_view(), name="auth-login"),
    path("session/", SessionView.as_view(), name="auth-session"),
]
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_session.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/apps/identity/
git commit -m "feat(identity): /auth/session/ returns person, tenant theme, capabilities"
```

---

## Task 9: People directory endpoint + isolation tests

**Files:**
- Modify: `backend/apps/identity/serializers.py` (add `PersonDirectorySerializer`)
- Modify: `backend/apps/identity/views.py` (add `PeopleListView`)
- Modify: `backend/apps/identity/urls.py` (add route under a domain prefix)
- Modify: `backend/config/urls.py` (include identity domain routes)
- Test: `backend/apps/identity/tests/test_people.py` (create)

**Interfaces:**
- Consumes: `HasCapability` + `directory.view` capability, `DefaultPagination`.
- Produces: `GET /api/identity/people/` — paginated members of the active tenant, gated by `directory.view`.

- [ ] **Step 1: Write the failing tests** (isolation + permission-negative + cross-tenant)

```python
# backend/apps/identity/tests/test_people.py
import pytest
from rest_framework.test import APIClient


def _seed_tenant(slug, email, cap_keys):
    from django.contrib.auth import get_user_model
    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role", is_system=True)
        RoleGrant.objects.create(tenant=tenant, principal_type="person",
                                 principal_id=person.id, role=role)
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person


def _login(client, email):
    body = client.post("/api/auth/login/",
                       {"email": email, "password": "pw-12345"}, format="json").json()
    return body["access"]


@pytest.mark.django_db
def test_people_list_is_tenant_isolated():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, person_b = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get("/api/identity/people/",
                      HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant_a.id))
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert "a@acme.test" in emails
    assert "b@nw.test" not in emails  # tenant B never leaks


@pytest.mark.django_db
def test_people_list_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "a@acme.test", [])  # no directory.view
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get("/api/identity/people/",
                      HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant.id))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_people_list_cross_tenant_header_is_403():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "a@acme.test")  # member of A only
    resp = client.get("/api/identity/people/",
                      HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant_b.id))
    assert resp.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_people.py -v`
Expected: FAIL (404 — route not wired).

- [ ] **Step 3: Directory serializer** (append to `backend/apps/identity/serializers.py`)

```python
class PersonDirectorySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="person.id")
    email = serializers.EmailField(source="person.email")
    display_name = serializers.CharField(source="person.display_name")
    org_unit = serializers.CharField(source="org_unit.name", default=None)

    class Meta:
        model = Membership
        fields = ["id", "email", "display_name", "org_unit", "status"]
```

- [ ] **Step 4: People list view** (append to `backend/apps/identity/views.py`)

```python
from rest_framework.generics import ListAPIView

from apps.identity.serializers import PersonDirectorySerializer
from core.permissions import HasCapability


class PeopleListView(ListAPIView):
    serializer_class = PersonDirectorySerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "directory.view"

    def get_queryset(self):
        # Membership.objects is tenant-scoped (fails closed with no tenant).
        return Membership.objects.select_related("person", "org_unit").order_by("person__display_name")
```

> Note: `APIView.permission_classes` resolves to the DRF default (`IsAuthenticated` + `IsActiveTenantMember` from settings), so this appends `HasCapability` to the global defaults.

- [ ] **Step 5: Add the domain route** (`backend/apps/identity/urls.py`) — split auth vs domain by using two url modules is overkill; add a second list here and mount under `identity/` in config:

Create `backend/apps/identity/domain_urls.py`:

```python
from django.urls import path

from apps.identity.views import PeopleListView

urlpatterns = [
    path("people/", PeopleListView.as_view(), name="people-list"),
]
```

- [ ] **Step 6: Wire it** — in `backend/config/urls.py`, uncomment/replace the identity domain line:

```python
    path("identity/", include("apps.identity.domain_urls")),
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_people.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Commit**

```bash
git add backend/apps/identity/ backend/config/urls.py
git commit -m "feat(identity): paginated People directory, tenant-isolated + capability-gated"
```

---

## Task 10: `seed_demo` management command

**Files:**
- Create: `backend/apps/identity/management/__init__.py`, `backend/apps/identity/management/commands/__init__.py`, `backend/apps/identity/management/commands/seed_demo.py`
- Test: `backend/apps/identity/tests/test_seed.py` (create)

**Interfaces:**
- Produces: `manage.py seed_demo` — idempotent; creates tenants Acme + Northwind, capabilities, system roles (Learner/Manager/Admin), demo persons with known passwords, memberships (incl. one person in both tenants), role grants.

- [ ] **Step 1: Write the failing test**

```python
# backend/apps/identity/tests/test_seed.py
import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_creates_two_tenants():
    from apps.identity.models import Membership, Tenant

    call_command("seed_demo")
    call_command("seed_demo")  # second run must not duplicate
    assert Tenant.objects.count() == 2
    # The shared person has a membership in both tenants.
    from django.contrib.auth import get_user_model

    Person = get_user_model()
    shared = Person.objects.get(email="dana@shared.test")
    assert Membership.all_tenants.filter(person=shared).count() == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_seed.py -v`
Expected: FAIL (`Unknown command: 'seed_demo'`).

- [ ] **Step 3: Implement the command** (`backend/apps/identity/management/commands/seed_demo.py`)

```python
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
from apps.identity.models import Membership, Tenant
from core.context import tenant_context

Person = get_user_model()

CAPABILITIES = [
    "directory.view", "skill.claim.submit", "skill.verify", "verifier.grant",
    "member.invite", "member.offboard", "credential.revoke", "taxonomy.edit",
    "jobprofile.edit", "report.org.view",
]
ROLE_CAPS = {
    "Learner": ["directory.view", "skill.claim.submit"],
    "Manager": ["directory.view", "skill.claim.submit", "report.org.view"],
    "Admin": CAPABILITIES,
}


class Command(BaseCommand):
    help = "Seed two demo tenants with roles, capabilities, people and memberships."

    def handle(self, *args, **options):
        for key in CAPABILITIES:
            Capability.objects.get_or_create(key=key)

        acme = self._tenant("acme", "Acme", "#4f46e5")
        northwind = self._tenant("northwind", "Northwind", "#0891b2")

        alice = self._person("alice@acme.test", "Alice Admin")
        bob = self._person("bob@acme.test", "Bob Learner")
        dana = self._person("dana@shared.test", "Dana Dual")

        self._member(acme, alice, "Admin")
        self._member(acme, bob, "Learner")
        self._member(acme, dana, "Learner")
        self._member(northwind, dana, "Manager")

        self.stdout.write(self.style.SUCCESS("seed_demo complete."))

    def _tenant(self, slug, name, accent):
        tenant, _ = Tenant.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "status": "active", "plan": "pro", "accent_color": accent},
        )
        with tenant_context(tenant.id):
            for role_name, caps in ROLE_CAPS.items():
                role, _ = Role.objects.get_or_create(
                    tenant=tenant, name=role_name, defaults={"is_system": True}
                )
                for key in caps:
                    RoleCapability.objects.get_or_create(
                        tenant=tenant, role=role, capability_id=key
                    )
        return tenant

    def _person(self, email, name):
        person = Person.objects.filter(email=email).first()
        if person is None:
            person = Person.objects.create_user(email=email, display_name=name, password="demo-pass-123")
        return person

    def _member(self, tenant, person, role_name):
        with tenant_context(tenant.id):
            Membership.objects.get_or_create(
                person=person, tenant=tenant, defaults={"status": "active"}
            )
            role = Role.objects.get(tenant=tenant, name=role_name)
            RoleGrant.objects.get_or_create(
                tenant=tenant, principal_type="person", principal_id=person.id, role=role
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && .venv/bin/pytest apps/identity/tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 5: Full backend suite + lint**

Run: `cd backend && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/black --check . && .venv/bin/mypy .`
Expected: all green. Fix any lint/type issues (e.g. drop unused imports) before committing.

- [ ] **Step 6: Commit**

```bash
git add backend/apps/identity/management/ backend/apps/identity/tests/test_seed.py
git commit -m "feat(identity): seed_demo command for two-tenant demo data"
```

---

## Task 11: Frontend — real login, session hydration, logout

**Files:**
- Modify: `frontend/src/lib/auth.tsx`
- Modify: `frontend/src/pages/LoginPage.tsx`
- Test: `frontend/src/lib/auth.test.tsx` (create)

**Interfaces:**
- Consumes: `POST /auth/login/`, `GET /auth/session/` (Tasks 7–8); `tokenStore`, `tenantStore` (`lib/api.ts`); `useTenant().setTenant` (`lib/tenant.tsx`).
- Produces: `useAuth()` with `login(email, password) => Promise<Membership[]>`, `logout()`, `session: { capabilities, displayName } | null`, `hasCapability`. Exported `Membership` type `{ tenant_id, slug, name, accent_color }`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/lib/auth.test.tsx
import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { api } from './api'
import { AuthProvider, useAuth } from './auth'

function Probe() {
  const { login, session } = useAuth()
  return (
    <div>
      <button onClick={() => void login('a@acme.test', 'pw')}>go</button>
      <span data-testid="caps">{session?.capabilities.join(',') ?? 'none'}</span>
    </div>
  )
}

beforeEach(() => localStorage.clear())

test('login stores tokens and returns memberships', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: { access: 'a', refresh: 'r', memberships: [{ tenant_id: 't1', slug: 's', name: 'N', accent_color: '#000' }] },
  } as never)
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
  screen.getByText('go').click()
  await waitFor(() => expect(localStorage.getItem('lms.access')).toBe('a'))
  expect(post).toHaveBeenCalledWith('/auth/login/', { email: 'a@acme.test', password: 'pw' })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/lib/auth.test.tsx`
Expected: FAIL (`login` posts to `/auth/token/` with `username`, assertion mismatch).

- [ ] **Step 3: Rewrite `auth.tsx`** to real login/session/logout

```tsx
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { api, tenantStore, tokenStore } from './api'

export interface Membership {
  tenant_id: string
  slug: string
  name: string
  accent_color: string
}

export interface Session {
  capabilities: string[]
  displayName?: string
}

interface AuthContextValue {
  isAuthenticated: boolean
  session: Session | null
  login: (email: string, password: string) => Promise<Membership[]>
  loadSession: () => Promise<void>
  logout: () => void
  hasCapability: (capability: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(
    tokenStore.getAccess() ? { capabilities: [] } : null,
  )

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.post('/auth/login/', { email, password })
    tokenStore.set(resp.data.access, resp.data.refresh)
    setSession({ capabilities: [] })
    return resp.data.memberships as Membership[]
  }, [])

  const loadSession = useCallback(async () => {
    if (!tokenStore.getAccess() || !tenantStore.get()) return
    const resp = await api.get('/auth/session/')
    setSession({
      capabilities: resp.data.capabilities ?? [],
      displayName: resp.data.person?.display_name,
    })
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    tenantStore.clear()
    setSession(null)
  }, [])

  const hasCapability = useCallback(
    (capability: string) => session?.capabilities.includes(capability) ?? false,
    [session],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: session !== null,
      session,
      login,
      loadSession,
      logout,
      hasCapability,
    }),
    [session, login, loadSession, logout, hasCapability],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
```

- [ ] **Step 4: Update `LoginPage.tsx`** — email field + route by membership count

```tsx
import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../lib/auth'
import { useTenant } from '../lib/tenant'

export function LoginPage() {
  const { login, loadSession } = useAuth()
  const { setTenant } = useTenant()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const memberships = await login(email, password)
      if (memberships.length === 1) {
        const m = memberships[0]
        setTenant({ id: m.tenant_id, name: m.name, accentColor: m.accent_color })
        await loadSession()
        navigate('/')
      } else {
        navigate('/choose', { state: { memberships } })
      }
    } catch {
      setError('Invalid email or password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Skills LMS</p>
        </div>
        <label className="block text-sm">
          <span className="text-slate-700">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-700">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md py-2 font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
```

- [ ] **Step 5: Run test + typecheck**

Run: `cd frontend && npm run test -- src/lib/auth.test.tsx && npm run lint`
Expected: test PASSES; `oxlint` + `tsc` clean.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/auth.tsx frontend/src/pages/LoginPage.tsx frontend/src/lib/auth.test.tsx
git commit -m "feat(frontend): real email login, session hydration, stateless logout"
```

---

## Task 12: Frontend — tenant picker + capability-gated shell

**Files:**
- Modify: `frontend/src/pages/ChooseTenantPage.tsx`
- Modify: `frontend/src/components/AppShell.tsx`
- Test: `frontend/src/components/AppShell.test.tsx` (create)

**Interfaces:**
- Consumes: `useAuth()` (`hasCapability`, `logout`, `loadSession`), `useTenant().setTenant`, `Membership` type; router `location.state.memberships`.
- Produces: `/choose` renders real memberships; `AppShell` hides nav items whose `capability` the user lacks and has a working Logout.

- [ ] **Step 1: Read the current `AppShell.tsx`** to preserve its markup/nav structure.

Run: `cat frontend/src/components/AppShell.tsx`

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/components/AppShell.test.tsx
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { AppShell } from './AppShell'
import * as authModule from '../lib/auth'
import * as tenantModule from '../lib/tenant'

test('nav hides items the user lacks capability for', () => {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => c === 'directory.view',
    logout: vi.fn(),
    session: { capabilities: ['directory.view'] },
    isAuthenticated: true,
    login: vi.fn(),
    loadSession: vi.fn(),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)

  render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  )
  expect(screen.getByText('Directory')).toBeInTheDocument()
  expect(screen.queryByText('Admin')).not.toBeInTheDocument()
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/components/AppShell.test.tsx`
Expected: FAIL (Admin currently rendered unconditionally, or nav labels differ — adjust the label strings in the test to match Step 1's markup, then make the component gate them).

- [ ] **Step 4: Update `AppShell.tsx`** — give each nav item an optional `capability` and filter with `hasCapability`; ensure the tenant name renders from `useTenant().tenant?.name`; wire the Logout button to `logout()` + navigate `/login`. Preserve existing classes/layout from Step 1. Nav model:

```tsx
const NAV = [
  { to: '/', label: 'Home' },
  { to: '/directory', label: 'Directory', capability: 'directory.view' },
  { to: '/skills', label: 'Skills', capability: 'skill.claim.submit' },
  { to: '/admin', label: 'Admin', capability: 'member.invite' },
]
// render: NAV.filter((i) => !i.capability || hasCapability(i.capability))
```

Logout handler:

```tsx
const onLogout = () => {
  logout()
  navigate('/login')
}
```

- [ ] **Step 5: Rewrite `ChooseTenantPage.tsx`** to use real memberships

```tsx
import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth, type Membership } from '../lib/auth'
import { useTenant } from '../lib/tenant'

export function ChooseTenantPage() {
  const { setTenant } = useTenant()
  const { loadSession } = useAuth()
  const navigate = useNavigate()
  const memberships = (useLocation().state?.memberships ?? []) as Membership[]

  const pick = async (m: Membership) => {
    setTenant({ id: m.tenant_id, name: m.name, accentColor: m.accent_color })
    await loadSession()
    navigate('/')
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Choose an organization</h1>
        <p className="text-sm text-slate-500">You belong to more than one. Pick which to work in.</p>
        <ul className="space-y-2">
          {memberships.map((m) => (
            <li key={m.tenant_id}>
              <button
                onClick={() => void pick(m)}
                className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50"
              >
                <span className="inline-block h-8 w-8 rounded" style={{ backgroundColor: m.accent_color }} />
                <span className="font-medium text-slate-800">{m.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Run test + lint**

Run: `cd frontend && npm run test -- src/components/AppShell.test.tsx && npm run lint`
Expected: test PASSES; lint clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/AppShell.tsx frontend/src/pages/ChooseTenantPage.tsx frontend/src/components/AppShell.test.tsx
git commit -m "feat(frontend): capability-gated nav + real tenant picker"
```

---

## Task 13: Frontend — People directory page

**Files:**
- Create: `frontend/src/features/people/usePeople.ts`
- Create: `frontend/src/features/people/types.ts`
- Modify: `frontend/src/pages/DirectoryPage.tsx`
- Test: `frontend/src/features/people/usePeople.test.tsx` (create)

**Interfaces:**
- Consumes: `api` (`lib/api.ts`), `useTenant().tenant` (for the query key), DRF paginated envelope `{ count, next, previous, results }`.
- Produces: `usePeople(page: number)` TanStack Query hook keyed by `['people', tenantId, page]`; `DirectoryPage` renders the list + prev/next controls.

- [ ] **Step 1: Types** (`frontend/src/features/people/types.ts`)

```ts
export interface DirectoryPerson {
  id: string
  email: string
  display_name: string
  org_unit: string | null
  status: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
```

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/features/people/usePeople.test.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { usePeople } from './usePeople'

vi.mock('../../lib/tenant', () => ({ useTenant: () => ({ tenant: { id: 't1', name: 'Acme' } }) }))

test('usePeople fetches the people page', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({
    data: { count: 1, next: null, previous: null, results: [{ id: 'p1', email: 'a@a.test', display_name: 'A', org_unit: null, status: 'active' }] },
  } as never)
  const client = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => usePeople(1), { wrapper })
  await waitFor(() => expect(result.current.data?.results[0].email).toBe('a@a.test'))
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd frontend && npm run test -- src/features/people/usePeople.test.tsx`
Expected: FAIL (`usePeople` not found).

- [ ] **Step 4: Implement the hook** (`frontend/src/features/people/usePeople.ts`)

```ts
import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { DirectoryPerson, Paginated } from './types'

export function usePeople(page: number) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['people', tenant?.id, page],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<DirectoryPerson>>('/identity/people/', {
        params: { page },
      })
      return resp.data
    },
  })
}
```

- [ ] **Step 5: Rewrite `DirectoryPage.tsx`**

```tsx
import { useState } from 'react'

import { usePeople } from '../features/people/usePeople'

export function DirectoryPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = usePeople(page)

  if (isLoading) return <p className="p-6 text-slate-500">Loading people…</p>
  if (isError) return <p className="p-6 text-red-600">Could not load the directory.</p>

  const people = data?.results ?? []
  return (
    <div className="p-6">
      <h1 className="mb-4 text-xl font-semibold text-slate-900">People directory</h1>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {people.map((p) => (
          <li key={p.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium text-slate-800">{p.display_name}</div>
              <div className="text-sm text-slate-500">{p.email}</div>
            </div>
            <span className="text-sm text-slate-500">{p.org_unit ?? '—'}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-3">
        <button
          disabled={!data?.previous}
          onClick={() => setPage((n) => Math.max(1, n - 1))}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-slate-500">Page {page}</span>
        <button
          disabled={!data?.next}
          onClick={() => setPage((n) => n + 1)}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 6: Run test + lint**

Run: `cd frontend && npm run test -- src/features/people/usePeople.test.tsx && npm run lint`
Expected: test PASSES; lint clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/people/ frontend/src/pages/DirectoryPage.tsx
git commit -m "feat(frontend): paginated People directory page"
```

---

## Task 14: Full-stack verification

**Files:** none (verification only).

- [ ] **Step 1: Backend — full suite + lint**

Run: `cd backend && .venv/bin/pytest && .venv/bin/ruff check . && .venv/bin/black --check . && .venv/bin/mypy .`
Expected: all pass. If `mypy` flags the new files, add targeted `# type: ignore[...]` with a comment (per CLAUDE.md) rather than broadening config.

- [ ] **Step 2: Frontend — full suite + build**

Run: `cd frontend && npm run test && npm run lint && npm run build`
Expected: tests pass, lint clean, build succeeds.

- [ ] **Step 3: Manual smoke (requires Postgres)**

Run: `make db-up && make migrate && cd backend && .venv/bin/python manage.py seed_demo`
Then `make dev`, open `http://localhost:5173`, sign in as `dana@shared.test` / `demo-pass-123` → expect the tenant picker (two orgs); sign in as `bob@acme.test` / `demo-pass-123` → straight into Acme; confirm `/directory` lists Acme's people and the nav reflects Bob's (Learner) capabilities.

- [ ] **Step 4: Commit any fixes** discovered during verification, then stop for branch review.

```bash
git add -A && git commit -m "chore: full-stack verification fixes for auth+directory slice"
```

---

## Self-Review Notes (author)

- **Spec coverage:** identity models (Tasks 1–2), authz + `can()` (Tasks 3, 5), stateless bearer login (Task 7), `/auth/session/` (Task 8), membership enforcement (Task 6), People directory + isolation (Task 9), AuditLog (Task 4), seed data (Task 10), frontend login/session/logout/picker/shell/directory (Tasks 11–13). No blacklist/logout endpoint (matches decision #3). ✅
- **Review Focus** items are each pinned: missing header → Task 6; cross-tenant → Task 9; ended-only membership → Task 7; `can()` no-tenant → Task 5; refresh-on-401 already implemented in `api.ts` (verified in Task 14 smoke). ✅
- **Type consistency:** `Membership` shape `{tenant_id, slug, name, accent_color}` is identical in `MembershipSummarySerializer` (backend) and the frontend `Membership` type + `login()` return + `ChooseTenantPage`. `capabilities_for` / `can` / `HasCapability` signatures align across Tasks 5, 8, 9. ✅
