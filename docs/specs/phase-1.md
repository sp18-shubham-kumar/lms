# Phase 1 — Foundation

> Source: `docs/Skills_LMS_Requirements_Tasks_Subtasks.docx` §2–3.
> Goal: two organisations can coexist, nobody can see across, people can declare
> and browse skills. This is the "Spine" stage of the [roadmap](./roadmap.md).

## Requirements

| ID | Requirement | Owner |
| --- | --- | --- |
| P1-R1 | Create tenant/organization and establish tenant context | Backend |
| P1-R2 | Create person, membership and org-unit model | Backend |
| P1-R3 | Implement authentication/sign-in flow for demo | Backend + Frontend |
| P1-R4 | Implement roles/capabilities and basic authorization | Backend |
| P1-R5 | Create skill CRUD and seed initial skills | Backend |
| P1-R6 | Allow users to declare/remove their own skills | Backend + Frontend |
| P1-R7 | Build people directory with skill/org-unit filters | Frontend + Backend |
| P1-R8 | Implement tenant isolation and audit logging | Backend |
| P1-R9 | Add admin flow for member import/invite | Backend + Frontend |
| P1-R10 | Add automated tests for isolation and permissions | QA + Backend |

## Subtasks

**Data & scoping**
- Implement tenant / person / membership / org-unit tables (`apps/identity`).
- Implement role, capability and grant tables (`apps/authz`).
- Implement skill and self-declared-skill tables (`apps/skills`).
- Create database migrations and seed data.
- Confirm the tenant-scoped manager/service pattern (already scaffolded in `core/`).
- Add tenant isolation policy tests (extend `core/tests/test_tenant_isolation.py`).

**API**
- Build authentication/session endpoint(s) — JWT + a `/auth/session/` returning the
  user, capability set, and active tenant theme.
- Build skill CRUD endpoints.
- Build self-declared-skill endpoints (declare / remove own skills).
- Build people search/filter endpoint (by skill, by org unit).
- Build admin member import/invite flow (CSV with a dry-run diff before commit).
- Add audit middleware/logging (wire `core.audit.record` + concrete `AuditLog` model).

**Frontend**
- Learner profile page.
- People directory page (with filters).
- Skill declaration UI.

**Quality**
- Add API / unit / integration tests.
- Prepare staging/demo seed data.

## Acceptance (Definition of Done)

- Works end-to-end on staging; API + UI meet agreed acceptance criteria.
- Tenant isolation and permission **negative** cases are tested (tenant A cannot see B;
  a user without a capability is denied with a reason).
- Migrations are committed and reproducible.
- State-changing actions are auditable.
- Demo data is seeded; the demo script runs without manual DB edits.

## Provable claim at the end

> Two organisations can coexist and nobody can see across. People can declare skills
> and appear in a filterable directory.
