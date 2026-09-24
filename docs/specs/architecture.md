# Architecture

> Distilled from `docs/Skills_LMS_Project_Overview_.docx`, `docs/Skills_LMS_Requirements_Tasks_Subtasks.docx`,
> and the two `docs/skills-lms-*.html` source documents. Those are the source of
> truth; this file is the Claude-readable summary. When in doubt, re-read the source.

## What we're building

An internal, **multi-tenant Skills LMS**. It helps team members understand what to
learn, tracks their skills and progress, and gives managers a clear view of team
capability and gaps.

Three commitments shape every decision:

1. **Content is not the product.** People learn anywhere (YouTube, books, colleagues).
   The platform tracks *skills*, not course completions — nothing depends on hosting content.
2. **Verification is permission-based.** Each organisation nominates who may confirm
   which skill at which level. That rule is **data, not code** (`verifier_authority`).
3. **Two-tier confidence.** A self-claim and a verified assertion are *separate records*.
   Reports, promotions, and rewards read only the verified tier.

## Users

- **Learner** — understand skills and learning needs.
- **Manager / Team Lead** — understand team capability and gaps.
- **Admin** — manage people, skills, roles, and organization data.

Most people are two of these at once → **one shell, sections gated by capability**
(not three separate apps).

## System shape

```
Users → Frontend (Vite/React SPA) → Backend (DRF API) ↔ Postgres
```

- **Backend**: a **modular monolith** (Django project, one app per module boundary).
  Modules own their tables and talk through service interfaces, never raw cross-module
  joins — this keeps a later extraction possible.
- **One deployment, one database, many tenants.** Shared schema; every domain row
  carries `tenant_id`.
- **The gateway rule**: every request resolves to exactly one tenant *before* it
  touches a module (`core.middleware.TenantContextMiddleware` + `TenantScopedManager`).

## Module boundaries (Django apps)

| App (`backend/apps/…`) | Owns | Phase |
| --- | --- | --- |
| `identity` | tenant, person, membership, org_unit, identity_provider | 1 |
| `authz` | capability, role, role_grant, verifier_authority, `can()` | 1 (authority: 2+) |
| `skills` | skill_domain, skill, self-declared skill; levels/edges/overrides | 1 + 2 |
| `profiles` | track, job_profile, profile_requirement, readiness_snapshot | 2 |
| `core` | shared base models, tenant scoping, permissions, audit, pagination | — |

The full spec also describes later modules (catalog, roadmaps, assessment, verify,
credentials, rewards, events, automation, admin — "C5–C13"). They are **out of scope
for Phase 1/2** but the app layout leaves room for them.

## Authorization: two different systems

- **Capability** — "may this person *ever* do X?" (e.g. `skill.verify`). From role grants.
- **Authority** — "may they do X to *this* resource?" (e.g. verify *this* skill at
  *this* level for *this* org subtree). From `verifier_authority`.

Everything funnels through one entry point: `can(actor, capability, resource)`,
**deny by default**. See `backend/core/permissions.py`.

Seeded capabilities include: `skill.claim.submit` (everyone), `skill.verify` (verifiers),
`verifier.grant` / `member.invite` / `member.offboard` / `credential.revoke` (org admin),
`taxonomy.edit` / `jobprofile.edit` (L&D admin), `report.org.view` (manager, scoped to subtree).

## Isolation & audit (non-negotiable)

Tenants are competing companies; a cross-tenant read is a **breach, not a bug**. Layers:

1. **Application** — every query goes through a tenant-scoped repository/manager.
2. **Database** — (future) Postgres row-level security as defence in depth.
3. **Storage** — per-tenant key prefix, short-lived signed URLs (when evidence lands).
4. **Audit** — append-only log; nightly cross-tenant leak scan.

Chosen enforcement (from the approved plan): **shared schema + `tenant_id`, enforced
at the application layer** via `core.managers.TenantScopedManager`. Postgres RLS is a
documented later hardening step, not required for the MVP.

Isolation is tested directly: seed two tenants, run every list endpoint as tenant A,
assert **zero** rows from tenant B. This suite grows with every endpoint and is not optional.

## Frontend architecture

- One **shell**: tenant theme + session + capability gate + notifications. Sections
  (learner / verifier / admin) appear according to capabilities.
- Server state via **TanStack Query**, cache keyed by **tenant + resource**. Never
  cache across a tenant switch; clear on switch.
- Session payload carries capabilities + tenant theme + org scope → one request drives
  conditional rendering. The shell **hides** what can't be done rather than showing dead controls.
- Design tokens as **CSS custom properties** so tenant accent/logo apply without a rebuild.
- Writes to the assertion table / ledger are **pessimistic** (explicit confirmation),
  never optimistic.

## Backend architecture

- Tenant context is set per request before any query runs (fail closed).
- Every write endpoint takes an **idempotency key** (mobile clients retry).
- Background jobs carry tenant context **explicitly**; a worker with no tenant set must fail.
- Migrations run online: additive first, backfill, then a separate cleanup release.

See also: [data-model.md](./data-model.md) · [phase-1.md](./phase-1.md) ·
[phase-2.md](./phase-2.md) · [roadmap.md](./roadmap.md).
