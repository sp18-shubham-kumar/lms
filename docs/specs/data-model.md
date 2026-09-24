# Data model

> Transcribed from the MVP spec's schema blocks. Copy field names **exactly** when
> implementing models so specs and code line up. `tenant_id NULL` = a global/platform
> row shared across tenants; everything else is tenant-scoped.
>
> Implementation note: tenant-scoped models inherit `core.models.TenantScopedModel`
> (adds UUID `id`, `created_at`, `updated_at`, `tenant` FK, scoped manager).
> `Person` and `Tenant` are NOT tenant-scoped — they define/cross the boundary.

## Identity & tenancy (`apps/identity`) — Phase 1

```
person(id, email UNIQUE, display_name, did, created_at)
tenant(id, slug UNIQUE, name, status, plan, accent_color, logo_url)
org_unit(id, tenant_id, parent_id, name, path)           -- materialised path for subtree scope
membership(id, person_id, tenant_id, org_unit_id, job_profile_id,
           employee_ref, status, joined_at, ended_at)
           UNIQUE(person_id, tenant_id)                  -- one membership per person per tenant
identity_provider(id, tenant_id, kind, issuer, client_id, domain_hint)
```

- A **person is global**, not owned by a tenant; one person can hold memberships in
  multiple tenants and keeps credentials after memberships end.
- Login resolves email → person → active memberships. One membership → straight in;
  two or more → tenant picker.
- Ending a membership revokes sessions and hides the person from tenant reports, but
  **never deletes assertions** (verification history is the tenant's audit record).

## Authorization (`apps/authz`) — Phase 1 (authority resolution: Phase 2+)

```
capability(key)                          -- flat, seeded, NOT tenant-editable
role(id, tenant_id, name, is_system)
role_capability(role_id, capability_key)
role_grant(id, tenant_id, principal_type, principal_id, role_id,
           scope_type, scope_id)         -- principal: person | group

verifier_authority(id, tenant_id, principal_type, principal_id,
           skill_id NULL, skill_group_id NULL, max_level,
           scope_org_unit_id, requires_quorum, can_delegate,
           valid_from, valid_to, granted_by, revoked_at)
```

- One decision function: `can(actor, capability, resource)`, deny by default.
- Resolved capability set is cached per session; invalidate on any `role_grant` /
  `verifier_authority` write.
- Every **deny** is logged with the failing check (no silent "permission denied").

## Skills taxonomy (`apps/skills`) — Phase 1 CRUD, Phase 2 framework

```
skill_domain(id, tenant_id NULL, name, sort)
skill(id, tenant_id NULL, domain_id, name, slug,
      external_code, description, status, version)

-- Phase 1: the untrusted self-claim tier (separate from verified assertions)
self_declared_skill(id, tenant_id, membership_id, skill_id, level NULL, note, created_at)

-- Phase 2:
skill_level(id, skill_id, level SMALLINT,      -- 1..5
      title, indicators TEXT[], evidence_kinds TEXT[],
      min_verifier_level, validity_months)
skill_edge(from_skill_id, to_skill_id, kind)   -- prerequisite | adjacent ; must stay acyclic
tenant_skill_override(tenant_id, skill_id, name, status, hidden)   -- copy-on-write
```

- Global rows have `tenant_id IS NULL`; a tenant reads globals **left-joined** to its
  overrides (copy-on-write: renaming writes an override, leaves global untouched).
- Skills are **versioned, never mutated in place**. An assertion records the
  `skill_level` version it was judged against.
- Retiring a skill sets `status` and stops new claims; it never deletes (assertions point at it).
- Evidence type escalates with level (L1 quiz → L5 panel). That rule is what stops
  L5 from being "a quiz someone passed twice".

## Job profiles & readiness (`apps/profiles`) — Phase 2

```
track(id, tenant_id, name)                     -- Backend, Design, Sales
job_profile(id, tenant_id, track_id, grade SMALLINT, title, status)
profile_requirement(job_profile_id, skill_id, min_level, criticality)  -- core | supporting | optional
readiness_snapshot(membership_id, job_profile_id, met, total, blocking_skill_ids, computed_at)
```

- **Readiness is computed, not asserted**: count verified assertions meeting or
  exceeding each requirement.
- Recompute on any verified-assertion write for that person, plus nightly for everyone.
  Cached in `readiness_snapshot` (managers open team views that would otherwise fan out).
- **Core** requirements gate promotion; **supporting** are advisory.
- Promotion is deliberately **not automated** — the platform says "requirements met",
  an admin records the grade change.
- Changing a profile's requirements is **versioned**; anyone mid-roadmap stays on their version.

## Audit (`core`) — Phase 1

```
audit_log(id, tenant_id, actor_id, action, resource_type, resource_id, metadata JSONB, created_at)
```

- **Append-only** (never update or delete). Every state-changing action records one.
- Nightly job samples each tenant-scoped table for rows reachable under the wrong
  context and alerts on any hit.
