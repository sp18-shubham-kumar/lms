# Complete Backend — Phase 1 + Phase 2 (design)

> Date: 2026-10-01 · Scope approved: **Phase 1 (Spine) + Phase 2 (Map)**.
> Verification loop, credentials, rewards (Phase 3–5) are **out of scope**.
> Source of truth: `docs/specs/{architecture,data-model,phase-1,phase-2,roadmap}.md`
> and the original `docs/*.docx` / `docs/skills-lms-*.html`. This document records the
> delta to build on top of the existing scaffold and the decisions taken during
> brainstorming.

## Goal

Finish the backend so that, across two isolated tenants:

1. People declare/browse skills and appear in a filterable directory (Phase 1).
2. An org describes its own skill framework (levels, rubrics, prerequisites,
   tenant overrides, tracks, job profiles, requirements) and a learner/manager sees
   the gap between verified capability and a target grade (Phase 2).

Every endpoint is tenant-scoped, capability-gated, audited, and fully documented in
Swagger (`/api/schema/swagger-ui/`).

## What already exists (reuse, do not rebuild)

- **core**: `TenantScopedModel`/`TenantScopedManager`/context vars,
  `TenantContextMiddleware`, `can()` + `HasCapability` + `IsActiveTenantMember`,
  `audit.record` + `AuditLog`, `DefaultPagination`, exception handler.
- **identity**: `Person`, `Tenant`, `OrgUnit`, `Membership`, `IdentityProvider`;
  auth (`/api/auth/login`, `/api/auth/session`, token refresh); `/api/identity/people/`.
- **authz**: `Capability`, `Role`, `RoleCapability`, `RoleGrant` models (no endpoints).
- **Swagger**: drf-spectacular wired (`/api/schema/`, `/api/schema/swagger-ui/`).
- **seed_demo**, isolation/auth/permission tests.

## Decisions taken (brainstorming)

1. **Verified tier exists via a thin `SkillAssertion` table**, seeded + set through a
   minimal capability-gated admin endpoint. Readiness/gap/heatmap read **only** this
   table. **No** verifier queue / `VerifierAuthority` / evidence (Phase 3).
2. **Background work = management commands** (`recompute_readiness`, `scan_isolation`)
   plus **synchronous** readiness recompute on assertion writes. No Celery/broker.
3. **Idempotency**: write endpoints honor an `Idempotency-Key` header (architecture
   rule). Lightweight `core` helper; replays return the first result.
4. **Delivery**: one design (this doc) → two sequenced implementation plans
   (P1-completion, P2), each built TDD.

## Cross-cutting conventions (apply to every module)

- **Thin views + `services.py`**: readiness calc, versioning/publish, CSV import, cycle
  checks live in services; views/serializers stay declarative.
- **DRF `ModelViewSet` + routers** for CRUD; `APIView` for bespoke actions. Reads go
  through `Model.objects` (tenant-scoped, fail-closed). `all_tenants` only in
  provisioning/commands/isolation scan.
- **Capability gating** via `HasCapability` (`required_capability`) on every endpoint;
  deny is logged by `can()`.
- **Audit** every state-changing action with `core.audit.record`.
- **Swagger**: `@extend_schema` on every view/action — `summary`, `description`,
  request/response serializers, examples, and a module **tag** (`Identity`, `Authz`,
  `Skills`, `Profiles`). Serializers carry docstrings and `help_text`.
- **Immutability**: skills & job profiles are **versioned, never mutated in place**;
  **retire, never delete**; assertions/requirements/snapshots pin the version judged.
- **Isolation tests** for every list endpoint; **negative permission tests** for every
  capability. Not optional.

## Data model delta

Field names copied **exactly** from `docs/specs/data-model.md`. All tenant-scoped models
inherit `core.models.TenantScopedModel` (UUID id, created/updated, tenant FK, scoped
manager). `tenant_id NULL` = global/platform row.

### skills (Phase 1)

```
skill_domain(id, tenant_id NULL, name, sort)
skill(id, tenant_id NULL, domain_id, name, slug, external_code,
      description, status[draft|published|retired], version)
self_declared_skill(id, tenant_id, membership_id, skill_id, level NULL, note, created_at)
```

### skills (Phase 2)

```
skill_level(id, skill_id, level SMALLINT 1..5, title, indicators TEXT[],
            evidence_kinds TEXT[], min_verifier_level, validity_months)
skill_edge(id, tenant_id NULL, from_skill_id, to_skill_id, kind[prerequisite|adjacent])
tenant_skill_override(id, tenant_id, skill_id, name, status, hidden)   -- copy-on-write
skill_assertion(id, tenant_id, membership_id, skill_id, level,          -- VERIFIED tier
                skill_level_id, skill_version, verified_by_id, verified_at, note)
```

- Globals (`tenant_id NULL`) are read-only to tenants; a tenant reads globals
  **left-joined** to its `tenant_skill_override` rows (rename/hide without touching the
  global).
- **Versioning**: editing a *published* skill's definition/levels creates a new version
  (immutable prior version retained); `self_declared_skill`, `skill_assertion`,
  `profile_requirement` reference the specific version. `skill_edge` must stay acyclic —
  rejected in service on insert.
- `skill_assertion` is the **only** source readiness reads.

### profiles (Phase 2)

```
track(id, tenant_id, name)
job_profile(id, tenant_id, track_id, grade SMALLINT, title,
            status[draft|published|retired], version)
profile_requirement(id, tenant_id, job_profile_id, skill_id, min_level,
                    criticality[core|supporting|optional])
readiness_snapshot(id, tenant_id, membership_id, job_profile_id, met, total,
                   blocking_skill_ids UUID[], computed_at, job_profile_version)
```

- **Readiness is computed**: for each requirement, is there a verified assertion at/above
  `min_level`? `met/total` over **core** requirements gates; **supporting/optional** are
  advisory. `blocking_skill_ids` = unmet core requirements.
- Recompute synchronously on any `skill_assertion` write for that person, and in
  `recompute_readiness` (nightly-by-cron). Cached in `readiness_snapshot`.
- Changing a published profile's requirements is **versioned**; mid-roadmap learners stay
  on their snapshot's `job_profile_version`.

## API surface

All under `/api/`, JWT-authenticated, `X-Tenant-Id` scoped, paginated where lists.

### Phase 1

| Method | Path | Capability | Notes |
| --- | --- | --- | --- |
| GET | `/skills/domains/` | `directory.view` | list domains (globals + tenant) |
| GET/POST | `/skills/skills/` | read: `directory.view` · write: `taxonomy.edit` | create = tenant skill (draft) |
| GET/PATCH/DELETE | `/skills/skills/{id}/` | `taxonomy.edit` for write | DELETE = retire |
| GET/POST | `/skills/me/declarations/` | `skill.claim.submit` | own self-declared skills |
| DELETE | `/skills/me/declarations/{id}/` | `skill.claim.submit` | remove own |
| GET | `/identity/people/?skill=&org_unit=&level=` | `directory.view` | extend existing |
| POST | `/identity/members/import/` | `member.invite` | dry-run diff |
| POST | `/identity/members/import/?commit=true` | `member.invite` | apply; audited |
| GET | `/authz/roles/` | `member.invite` | roles + capabilities |
| GET/POST/DELETE | `/authz/grants/` | `member.invite`/`member.offboard` | manage role grants |

### Phase 2

| Method | Path | Capability | Notes |
| --- | --- | --- | --- |
| GET/PUT | `/skills/skills/{id}/levels/` | `taxonomy.edit` | rubric grid (1..5) |
| GET/POST/DELETE | `/skills/skills/{id}/edges/` | `taxonomy.edit` | reject cycles |
| POST | `/skills/skills/{id}/override/` | `taxonomy.edit` | copy-on-write |
| POST | `/skills/skills/{id}/publish/` | `taxonomy.edit` | snapshot version |
| GET/POST | `/skills/assertions/` | `skill.verify` | verified tier (minimal) |
| CRUD | `/profiles/tracks/` | `jobprofile.edit` | |
| CRUD | `/profiles/job-profiles/` (+ `/requirements/`, `/publish/`) | `jobprofile.edit` | |
| GET | `/profiles/me/readiness/?target=<profile>` | `skill.claim.submit` | learner gap view |
| GET | `/profiles/readiness/?job_profile=` | `report.org.view` | team, subtree-scoped |
| GET | `/profiles/heatmap/?org_unit=&job_profile=` | `report.org.view` | members × core reqs |

New capabilities to seed if missing: ensure `directory.view`, `skill.claim.submit`,
`taxonomy.edit`, `jobprofile.edit`, `member.invite`, `member.offboard`, `skill.verify`,
`report.org.view` exist and are granted to the right system roles.

## Security fix (Phase 1)

Complete the `TenantContextMiddleware` TODO: a request whose authenticated user has **no
active membership** in the `X-Tenant-Id` tenant is rejected (403), before any view runs.
Covered by `IsActiveTenantMember` at the DRF layer today, but enforce at the middleware
boundary too and add negative tests.

## Background jobs

- `manage.py recompute_readiness [--tenant <slug>]` — recompute all snapshots.
- `manage.py scan_isolation` — sample each tenant-scoped table for rows reachable under
  the wrong tenant context; exit non-zero + report on any hit.
- Synchronous recompute hook on `skill_assertion` create/update/delete.

## Testing

- **Isolation**: seed two tenants; every list endpoint returns zero of tenant B's rows.
- **Permissions**: every capability has a negative test (missing capability → 403 + log).
- **Units**: readiness math (core vs supporting, met/exceeds/blocking), version pinning,
  cycle rejection, override left-join, CSV import dry-run vs commit, idempotency replay.
- **Seed**: extend `seed_demo` with a Data Engineer L1/L2/L3 ladder, skills + levels,
  profile requirements, and verified assertions so gap/heatmap render truthfully.

## Out of scope (explicit)

Verifier queue, `VerifierAuthority` resolution, evidence upload/storage, credentials &
signing, public verify page, rewards ledger, automation, Postgres RLS, Celery. The app
layout leaves room for these; they are Phase 3+.
