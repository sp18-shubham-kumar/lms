# Design — Auth, `/session` identity endpoint & People Directory (Phase-1 slice)

> Date: 2026-09-25 · Branch: `basic-setup`
> Distilled specs are the source of truth: [phase-1.md](../../specs/phase-1.md),
> [architecture.md](../../specs/architecture.md), [data-model.md](../../specs/data-model.md).
> This document is the concrete implementation design for one vertical slice of Phase 1.

## Goal

A user can sign in with email + password, receive a **stateless bearer (JWT)** token,
land in a capability-gated shell themed for their active tenant, and browse a
**paginated People directory** scoped to that tenant. Two tenants coexist; neither can
see the other's people.

This proves the whole vertical: identity → authz → auth → session → a real tenant-scoped
list page.

## Decisions (settled with the user)

1. **Login = email + password.** `Person` gains a password; demo users are seeded with
   known passwords.
2. **`Person` IS the Django `AUTH_USER_MODEL`** (`identity.Person`). One global identity
   table; email is the username field. Set before the first migration.
3. **Stateless bearer tokens.** JWT access + refresh in the `Authorization: Bearer …`
   header. The server holds **no session state**. Logout is a client-side token discard.
   No `token_blacklist` app, no server-side revocation table.
4. **Frontend scope this iteration:** login → shell (session, tenant theme, logout) →
   People directory (first paginated index page). Skills catalog and directory
   search/filters are follow-ups.

## Non-goals (explicitly deferred)

- SSO / `identity_provider` login (Phase 2+). The model may be created but is unused for login.
- Authority resolution (`verifier_authority`) — Phase 2. Only the **capability** half of
  `can()` is implemented now.
- Directory search/filter by skill/org-unit (P1-R7 full form) — a follow-up; this slice
  ships the paginated list.
- Member CSV import/invite (P1-R9), skills CRUD (P1-R5/6), profiles (Phase 2).
- Server-side token revocation / blacklist (out by decision #3).

---

## Backend

### 1. `apps/identity` models

Field names copied exactly from `data-model.md`.

**`Person`** — global, **not** tenant-scoped; custom user model.
- `id` UUID PK, `email` (unique, `USERNAME_FIELD`), `display_name`, `did` (nullable),
  `created_at`.
- Django auth fields: `password`, `is_active` (default True), `is_staff`, `is_superuser`,
  `last_login`. Inherits `PermissionsMixin` + `AbstractBaseUser`.
- `PersonManager(BaseUserManager)` with `create_user(email, password, **)` and
  `create_superuser(...)`. `REQUIRED_FIELDS = ["display_name"]`.
- No `tenant` FK (a person crosses tenants and outlives memberships).

**`Tenant`** — global, **not** tenant-scoped (inherits `UUIDModel`/`TimeStampedModel` only).
- `slug` (unique), `name`, `status`, `plan`, `accent_color`, `logo_url`.

**`OrgUnit`** — `TenantScopedModel`.
- `parent` (self-FK, nullable), `name`, `path` (materialised path for subtree scope).

**`Membership`** — `TenantScopedModel`.
- `person` FK, `org_unit` FK (nullable), `job_profile_id` (nullable, deferred — plain
  UUID field or omit until profiles land; **omit** this iteration), `employee_ref`,
  `status`, `joined_at`, `ended_at` (nullable).
- `UNIQUE(person, tenant)` — one membership per person per tenant.

**`IdentityProvider`** — `TenantScopedModel`. Created per data-model (`kind`, `issuer`,
`client_id`, `domain_hint`) but **unused for login** this iteration.

> `AUTH_USER_MODEL = "identity.Person"` added to `config/settings/base.py`. Because no
> migrations exist yet, this is free now and painful later — it lands with this slice.

### 2. `apps/authz` models + `can()`

**Models** (per data-model):
- `Capability` — PK is `key` (string); flat, seeded, not tenant-editable.
- `Role` — `TenantScopedModel`; `name`, `is_system`.
- `RoleCapability` — join (`role`, `capability`). Tenant-scoped via role.
- `RoleGrant` — `TenantScopedModel`; `principal_type` (`person`|`group`), `principal_id`,
  `role`, `scope_type`, `scope_id` (scope nullable this iteration; org-subtree scoping is
  data, honoured when present).

**`can(actor, capability, resource=None)`** — replace the deny-stub:
- Resolve the actor's capability set **for the active tenant** (`core.context` tenant):
  role grants where `principal_id == actor.id` → roles → capabilities.
- Cache the resolved set on the request (per-request memo) to avoid re-querying.
- **Deny by default.** Every deny logs the failing check (actor, capability, tenant,
  reason) — no silent denials (per architecture.md).
- `resource`/authority branch remains a documented Phase-2 TODO.

**Seed data** (management command, see §7): capability keys from architecture.md
(`skill.claim.submit`, `skill.verify`, `verifier.grant`, `member.invite`,
`member.offboard`, `credential.revoke`, `taxonomy.edit`, `jobprofile.edit`,
`report.org.view`, plus `directory.view` for the People page). System roles per tenant:
**Learner**, **Manager**, **Admin**, mapped to capability subsets.

### 3. Auth endpoints

Custom login/session views layered on SimpleJWT. `TokenRefreshView` stays as-is.

**`POST /api/auth/login/`** — public (`AllowAny`, no tenant required).
- Body: `{ email, password }`.
- `authenticate(email, password)`; on success issue SimpleJWT access + refresh for the
  person.
- Response: `{ access, refresh, memberships: [{ tenant_id, slug, name, accent_color }] }`
  — only **active** memberships.
- Audited: `core.audit.record(action="auth.login", actor=person, ...)`.
- Errors: 400 invalid body, 401 bad credentials, 403 no active membership (can't enter
  any tenant).

**`GET /api/auth/session/`** — authenticated; **requires `X-Tenant-Id`**.
- Middleware has already set tenant context and verified membership (see §4).
- Response:
  ```json
  {
    "person":       { "id", "email", "display_name" },
    "tenant":       { "id", "name", "slug", "accent_color", "logo_url" },
    "capabilities": ["directory.view", "..."],
    "memberships":  [{ "tenant_id", "slug", "name", "accent_color" }]
  }
  ```
- `capabilities` computed from authz for this person in this tenant.

**Logout** — **no endpoint** (stateless, decided). The client discards its tokens
(frontend section). The server records nothing on logout; the short access-token lifetime
(30 min) bounds a discarded-but-not-expired token.

### 4. Tenant-context middleware — fill the TODO

`core/middleware.py` currently trusts `X-Tenant-Id` blindly. Now that `Membership` exists,
the membership assertion is enforced with a **DRF permission class**, not in the
middleware — because SimpleJWT authenticates in the DRF/view layer, so `request.user` is
still anonymous when `TenantContextMiddleware.process_request` runs. Design:
- Middleware keeps its single job: parse `X-Tenant-Id` → set tenant context (unchanged).
- New permission `IsActiveTenantMember` (in `core.permissions`), added to
  `DEFAULT_PERMISSION_CLASSES` alongside `IsAuthenticated`: for an authenticated request
  it asserts an **active** `Membership(person=request.user, tenant=current_tenant)` exists;
  else **403** (a cross-tenant probe is a breach, not a miss). Missing tenant header on a
  tenant-scoped endpoint → 400.
- Public routes (health, login, schema) opt out via `AllowAny` + empty
  `authentication_classes`, exactly as `HealthView` already does — so they carry no
  tenant/user and are unaffected.
- Guarantee: no authenticated tenant-scoped response is served for a tenant the user isn't
  an active member of.

### 5. People directory endpoint

**`GET /api/identity/people/`** — authenticated, tenant-scoped, gated by `directory.view`.
- Lists **members of the active tenant**: person display_name/email + org_unit + status,
  read through `Membership.objects` (tenant-scoped manager → fails closed).
- Paginated via `DefaultPagination` (25/page, `page`/`page_size`, max 200) — already
  configured globally.
- Uses `HasCapability` with `required_capability = "directory.view"`.

### 6. Audit

Concrete **`AuditLog`** model in `core` (per data-model: `tenant_id`, `actor_id`,
`action`, `resource_type`, `resource_id`, `metadata` JSONB, `created_at`), append-only.
`tenant` FK is **nullable** so pre-tenant events (login, which precedes tenant selection)
can be recorded; tenant-scoped events set it. `AuditLog` is **not** a `TenantScopedModel`
(it must record cross-context and null-tenant events) — it inherits `UUIDModel`/
`TimeStampedModel` and is written via a plain manager. `core.audit.record(...)` inserts a
row; it never updates or deletes. Wired on login now; every future state-changing action
calls it.

### 7. Seed command + fixtures

`manage.py seed_demo` (idempotent):
- Two tenants: **Acme** (`accent #4f46e5`), **Northwind** (`accent #0891b2`).
- Capabilities + system roles (Learner/Manager/Admin) per tenant.
- Demo persons with **known passwords**, incl. one person who is a member of **both**
  tenants (exercises the tenant picker) and users with different roles (exercises
  capability gating).
- Role grants tying persons → roles.

---

## Frontend (behind existing seams)

The scaffold already wires providers, router, `api.ts` (Bearer + `X-Tenant-Id` +
refresh-on-401). Changes fill placeholders:

- **`lib/auth.tsx`**
  - `login(email, password)` → `POST /auth/login/`; store `{access, refresh}`.
    If `memberships.length === 1` → `setTenant(...)` and go `/`; else → `/choose`.
  - On app load with a stored token + tenant → fetch `GET /auth/session/`, hydrate
    `session.capabilities` + `displayName`. On 401/failure → clear + redirect to login.
  - `logout()` → clear tokens, clear tenant, `resetForTenantSwitch()` (drop query cache),
    navigate `/login`. **No server call** (stateless).
  - `Session` interface gains `person`/`tenant` as needed.
- **`pages/LoginPage.tsx`** — `username` field → **email** (type=email, autocomplete).
  Route after login per membership count (remove the always-`/choose` shortcut).
- **`pages/ChooseTenantPage.tsx`** — replace `DEMO_TENANTS` with the real `memberships`
  from login (held in auth state or passed via router state).
- **`components/AppShell.tsx`** — nav items gated by `hasCapability`; tenant name + accent
  always visible (already themed via `--tenant-accent`).
- **`pages/DirectoryPage.tsx`** — real paginated list via a TanStack Query hook in
  **`features/people/`** (query key includes the tenant), with page controls. Replaces the
  `PagePlaceholder`.
- Keep the existing **`/directory`** route name.

---

## Testing (TDD)

**Backend (pytest):**
- **Tenant isolation** on `/api/identity/people/`: seed 2 tenants, list as A, assert
  **zero** of B's rows (extend `core/tests/test_tenant_isolation.py`).
- **Permission negative**: a member lacking `directory.view` → 403 with a reason; the deny
  is logged.
- **Cross-tenant rejection**: authenticated user of tenant A sends `X-Tenant-Id` of tenant
  B → 403.
- **Auth**: login success returns tokens + memberships; bad credentials → 401; no active
  membership → 403. `/auth/session/` returns correct capability set per role.
- **Model**: `Person.create_user`/`create_superuser`; `UNIQUE(person, tenant)` on
  `Membership`.

**Frontend (Vitest + RTL):**
- Login form submits email+password, stores tokens, routes by membership count.
- `hasCapability` gates nav (a capability absent → its nav item not rendered).
- Logout clears tokens + cache and redirects to `/login`.
- Directory page renders a paginated list and can page forward.

## Acceptance (this slice)

- Sign in with a seeded demo user (email+password) → bearer token issued.
- Single-membership user lands directly in the shell; dual-membership user sees the picker.
- Shell shows the active tenant's name/accent; nav reflects the user's capabilities.
- `/directory` shows a paginated list of that tenant's people, and **only** that tenant's.
- Isolation + permission-negative + cross-tenant tests are green.
- `seed_demo` runs clean and the demo flow needs no manual DB edits.

## Migration / ordering notes

- `AUTH_USER_MODEL` set **before** first `makemigrations` for `identity`.
- Migration order: `identity` (Person/Tenant first, then tenant-scoped models) → `authz`
  → `core.AuditLog`. All additive; no data to backfill (greenfield).
