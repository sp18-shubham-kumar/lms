# Complete Backend (Phase 1 + 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the Skills LMS backend through Phase 2 — skills taxonomy with levels/rubrics/prerequisites/overrides/versioning, a thin verified-assertion tier, tracks/job-profiles/requirements, and a readiness/gap/heatmap engine — all tenant-scoped, capability-gated, audited, and Swagger-documented.

**Architecture:** Modular monolith (Django/DRF). Thin views over per-app `services.py`; reads via the tenant-scoped manager (fail-closed); writes audited and idempotent; skills/profiles versioned (never mutated in place). Readiness is computed from the verified tier only, cached in `readiness_snapshot`, recomputed synchronously on assertion writes + via a management command.

**Tech Stack:** Python 3.11, Django 5.1, DRF 3.15, drf-spectacular, SimpleJWT, Postgres 16 (ArrayField), pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-complete-backend-design.md` (read it + `docs/specs/data-model.md` before each task).

## Global Constraints

- Every domain table inherits `core.models.TenantScopedModel` (UUID id, created/updated, tenant FK, scoped manager). Globals use a separate non-scoped base and `tenant_id NULL`.
- All request-path reads go through `Model.objects` (tenant-scoped). `all_tenants` only in seed/commands/isolation-scan.
- Authorization funnels through `core.permissions.can()`; every endpoint sets `required_capability` via `HasCapability`. Deny-by-default.
- Field names copied **verbatim** from `docs/specs/data-model.md`.
- Skills & job profiles are versioned, never mutated in place; **retire, never delete**; assertions/requirements/snapshots pin the version judged.
- Every state-changing action calls `core.audit.record`.
- Every view/action carries `@extend_schema` (summary, description, serializers, example) and a module tag.
- ArrayField requires `django.contrib.postgres`; Postgres only (already the case).

## Review Focus

- **No tenant context on a write** → endpoint must 403/empty, never leak or write cross-tenant (owned by Task 1 middleware test + every list task's isolation test).
- **Self-declared level above a skill's max level / absent level** → declaration validation rejects out-of-range `level` (Task 6).
- **Readiness when a requirement's skill has no verified assertion** → counts as unmet + lands in `blocking_skill_ids`, never crashes on null (Task 15).
- **Cyclic prerequisite insert (A→B→A, and self-edge A→A)** → rejected with 400 before save (Task 11).
- **Idempotency-Key replay of a create** → returns the first result, creates no duplicate row (Task 2).

---

## PART A — Phase 1 completion

### Task 1: Harden TenantContextMiddleware (membership check)

**Files:**
- Modify: `backend/core/middleware.py`
- Test: `backend/core/tests/test_tenant_membership_middleware.py` (create)

**Interfaces:**
- Consumes: `request.user` (authenticated Person), `X-Tenant-Id` header, `identity.Membership`.
- Produces: rejects (403 JSON) a request whose user has no `status="active"` Membership in the header tenant, before view dispatch; sets `request.tenant_id` otherwise.

- [ ] **Step 1: Failing test** — authenticated user of tenant A sends `X-Tenant-Id: <tenant B>`; assert 403 and body `{"detail": ...}`; a user with active membership passes (200 on `/api/auth/session/`). Also: ended membership → 403.
- [ ] **Step 2:** Run `pytest backend/core/tests/test_tenant_membership_middleware.py -v` → FAIL.
- [ ] **Step 3:** In middleware, after resolving the header tenant and when `request.user` is authenticated, query `Membership.all_tenants.filter(person=user, tenant_id=tid, status="active").exists()`; if not, return `JsonResponse({"detail": "Not a member of this tenant."}, status=403)` before setting context. Keep existing context set/reset.
- [ ] **Step 4:** Run tests → PASS. Run full `make test-backend` → PASS.
- [ ] **Step 5:** Commit `fix(core): reject requests for tenants the user isn't a member of`.

### Task 2: Idempotency-Key helper

**Files:**
- Create: `backend/core/idempotency.py`, `backend/core/migrations/XXXX_idempotencyrecord.py` (via makemigrations)
- Modify: `backend/core/models.py` (add `IdempotencyRecord`)
- Test: `backend/core/tests/test_idempotency.py` (create)

**Interfaces:**
- Produces: `idempotent(request, tenant_id, response_factory) -> Response`. `IdempotencyRecord(tenant, key, method, path, response_status, response_body JSONB, created_at)` with `UNIQUE(tenant, key, method, path)`. A mixin `IdempotentCreateMixin` for viewsets that wraps `create()`.

- [ ] **Step 1: Failing test** — POST with header `Idempotency-Key: k1` twice; second returns the first's body/status and creates exactly one row.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement model + helper: on first call run factory, persist status+body; on replay (same tenant+key+method+path) return stored. No header → run normally (skip store).
- [ ] **Step 4:** makemigrations + migrate (test db) + tests → PASS.
- [ ] **Step 5:** Commit `feat(core): idempotency-key handling for write endpoints`.

### Task 3: Skills app — SkillDomain + Skill models

**Files:**
- Modify: `backend/apps/skills/models.py`
- Create: `backend/apps/skills/migrations/0001_initial.py` (makemigrations)
- Test: `backend/apps/skills/tests/test_models.py` (create; package `tests/`)

**Interfaces:**
- Produces:
  - `SkillDomain` — base `UUIDModel, TimeStampedModel` (NOT tenant-scoped; `tenant = FK(Tenant, null=True, on_delete=CASCADE, related_name="+")`), fields `name`, `sort SmallInteger default 0`. Manager returns globals (`tenant__isnull=True`) ∪ current-tenant rows via a `visible()` method.
  - `Skill` — same base + nullable tenant, fields `domain FK(SkillDomain)`, `name`, `slug`, `external_code (blank)`, `description (blank)`, `status` in {draft,published,retired} default draft, `version SmallInteger default 1`. `UNIQUE(tenant, slug, version)`; `Meta.ordering = ["name"]`.

- [ ] **Step 1: Failing test** — create a global domain + skill (`tenant=None`) and a tenant skill; assert defaults (`status="draft"`, `version=1`); assert `str`.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement models (globals use a small `GlobalOrTenantModel` base or plain UUID/TimeStamped + nullable tenant — document choice in module docstring). makemigrations.
- [ ] **Step 4:** migrate + tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): SkillDomain and versioned Skill models`.

### Task 4: Skill serializers + read endpoints (domains, skills list/retrieve)

**Files:**
- Create: `backend/apps/skills/serializers.py`, `backend/apps/skills/views.py` (replace scaffold), `backend/apps/skills/urls.py` (wire router)
- Modify: `backend/config/urls.py` (uncomment `path("skills/", include("apps.skills.urls"))`)
- Test: `backend/apps/skills/tests/test_skills_read.py`

**Interfaces:**
- Consumes: `HasCapability`, `DefaultPagination`.
- Produces: `GET /api/skills/domains/` (`directory.view`), `GET /api/skills/skills/` + `GET /api/skills/skills/{id}/` (`directory.view`). Reads = globals + tenant rows (via manager `visible()`), with tenant overrides applied (override applied in Task 12; for now raw). ViewSet `SkillViewSet(ModelViewSet)` with `get_queryset` scoped; `@extend_schema(tags=["Skills"])`.

- [ ] **Step 1: Failing test** — seed global + tenant-A skill + tenant-B skill; as tenant A, `GET /skills/skills/` returns global + A, **never B** (isolation); missing `directory.view` → 403.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement serializers + ViewSet (read actions only enabled here) + router + url include + schema annotations.
- [ ] **Step 4:** tests + full backend tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): skill/domain read endpoints with isolation`.

### Task 5: Skill write endpoints (create/update/retire) — taxonomy.edit

**Files:**
- Modify: `backend/apps/skills/views.py`, `serializers.py`, `backend/apps/skills/services.py` (create)
- Test: `backend/apps/skills/tests/test_skills_write.py`

**Interfaces:**
- Produces: `POST /skills/skills/` (create tenant skill, draft), `PATCH /skills/skills/{id}/`, `DELETE /skills/skills/{id}/` = retire (`status="retired"`, not deleted). All `taxonomy.edit`, audited, idempotent create. `services.retire_skill(skill, actor)`. Global skills (`tenant=None`) are not writable by a tenant (403/400).

- [ ] **Step 1: Failing test** — create skill as `taxonomy.edit` holder → 201 draft; non-holder → 403; DELETE sets status retired and row still exists; attempt to PATCH a global skill → rejected; audit row written on create.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement write actions, service, audit, idempotency, capability per-action (`get_permissions`).
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): skill create/update/retire (taxonomy.edit), audited`.

### Task 6: SelfDeclaredSkill model + endpoints (own declarations)

**Files:**
- Modify: `backend/apps/skills/models.py` (add `SelfDeclaredSkill`), `serializers.py`, `views.py`, `urls.py`, migration
- Test: `backend/apps/skills/tests/test_declarations.py`

**Interfaces:**
- Produces: `SelfDeclaredSkill(TenantScopedModel)` — `membership FK(identity.Membership)`, `skill FK(Skill)`, `level SmallInteger null`, `note (blank)`. `UNIQUE(membership, skill)`. Endpoints: `GET/POST /skills/me/declarations/`, `DELETE /skills/me/declarations/{id}/` (`skill.claim.submit`). POST resolves the caller's membership in the active tenant; `level` validated 1..5 (and ≤ skill's max defined level if levels exist — else 1..5). Audited.

- [ ] **Step 1: Failing test** — declare a skill → 201 tied to caller's membership; duplicate declare → 400; `level=9` → 400; list returns only the caller's declarations (not other members'); delete own → 204; delete another member's → 404.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement model + migration + endpoints + validation + audit.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): self-declared skill declare/remove endpoints`.

### Task 7: Directory filters (skill, org_unit, level)

**Files:**
- Modify: `backend/apps/identity/views.py` (`PeopleListView`), `serializers.py` if needed
- Test: `backend/apps/identity/tests/test_people_filters.py`

**Interfaces:**
- Produces: `GET /api/identity/people/?skill=<id>&org_unit=<id>&level=<n>` filters active memberships by a verified **or** self-declared skill (document which — use verified `SkillAssertion` once Task 13 lands; until then self-declared), org unit subtree (materialised `path` prefix), and minimum level. Each filter isolation-tested.

- [ ] **Step 1: Failing test** — seed people across two tenants + org units + declarations; `?skill=` returns only matching tenant-A people; `?org_unit=` returns subtree members; combined filters AND; tenant B invisible throughout.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement filter logic in `get_queryset` (prefer `django_filters` if already a dep, else manual query params). Use org_unit `path` prefix for subtree.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(identity): directory filters by skill, org unit, level`.

### Task 8: Authz admin endpoints (roles, grants)

**Files:**
- Create: `backend/apps/authz/serializers.py`, replace `backend/apps/authz/views.py`, `backend/apps/authz/urls.py`
- Modify: `backend/config/urls.py` (enable `path("authz/", include("apps.authz.urls"))`)
- Test: `backend/apps/authz/tests/test_admin_endpoints.py`

**Interfaces:**
- Produces: `GET /api/authz/roles/` (role + capability keys, `member.invite`), `GET/POST/DELETE /api/authz/grants/` (manage `RoleGrant`; POST `member.invite`, DELETE `member.offboard`). Posting a grant invalidates the affected principal's cached capabilities (call existing invalidation if present, else note). Audited.

- [ ] **Step 1: Failing test** — list roles as admin → system roles + capabilities; create a grant → 201 + audit; non-admin → 403; grants isolation (A can't grant into B / see B's grants).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement serializers/views/urls/schema; audit.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(authz): role list and grant management endpoints`.

### Task 9: Member CSV import (dry-run diff + commit)

**Files:**
- Create: `backend/apps/identity/import_service.py`, serializers, view; wire url
- Test: `backend/apps/identity/tests/test_member_import.py`

**Interfaces:**
- Produces: `POST /api/identity/members/import/` (multipart/CSV or JSON rows) returns a diff `{"adds":[...],"updates":[...],"errors":[{"row":n,"reason":...}]}` without writing; `?commit=true` applies adds/updates (create Person if missing by email, create/update Membership, attach role) and audits. `member.invite`. Idempotent commit (Idempotency-Key). CSV columns: `email,display_name,org_unit_path,role,employee_ref`.

- [ ] **Step 1: Failing test** — dry-run returns adds/errors, writes nothing (DB counts unchanged); commit creates persons+memberships; malformed row → in `errors`, not committed; re-POST same commit with same Idempotency-Key → no duplicates.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement parser + diff + commit service + endpoint + audit + idempotency.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(identity): member CSV import with dry-run diff and commit`.

### Task 10: Capability/seed reconciliation + Part A Swagger pass

**Files:**
- Modify: `backend/apps/identity/management/commands/seed_demo.py`
- Modify: any Part A view missing `@extend_schema`
- Test: `backend/apps/identity/tests/test_seed.py` (extend), `backend/core/tests/test_schema.py` (create)

**Interfaces:**
- Produces: seed ensures all capabilities (`directory.view, skill.claim.submit, taxonomy.edit, jobprofile.edit, member.invite, member.offboard, skill.verify, report.org.view`) exist and are granted to Learner/Manager/Admin appropriately; seeds a few global skills+domains. `test_schema` asserts `GET /api/schema/` returns 200 and contains each new path with a summary/tag.

- [ ] **Step 1: Failing test** — schema test asserts presence of `/api/skills/skills/`, `/api/skills/me/declarations/`, `/api/authz/grants/`, `/api/identity/members/import/` with tags; seed test asserts capability grants.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Fill schema annotations; update seed.
- [ ] **Step 4:** tests + `make lint-backend` → PASS/clean.
- [ ] **Step 5:** Commit `chore(backend): seed capabilities + complete Part A Swagger docs`.

---

## PART B — Phase 2 (framework + readiness)

### Task 11: SkillLevel + SkillEdge models (+ acyclic service)

**Files:**
- Modify: `backend/apps/skills/models.py`, `backend/apps/skills/services.py`, migration
- Test: `backend/apps/skills/tests/test_levels_edges.py`

**Interfaces:**
- Produces:
  - `SkillLevel` (UUID/TimeStamped, not tenant-scoped; belongs to a skill) — `skill FK`, `level SmallInteger` (1..5, validators), `title`, `indicators ArrayField(TextField)`, `evidence_kinds ArrayField(TextField)`, `min_verifier_level SmallInteger null`, `validity_months SmallInteger null`. `UNIQUE(skill, level)`.
  - `SkillEdge(GlobalOrTenant)` — `from_skill`, `to_skill`, `kind` in {prerequisite,adjacent}. `UNIQUE(from_skill,to_skill,kind)`.
  - `services.add_edge(from_skill, to_skill, kind)` raises `ValidationError` on self-edge or if adding a `prerequisite` edge introduces a cycle (DFS over prerequisite edges). `services.would_create_cycle(from_id, to_id) -> bool`.

- [ ] **Step 1: Failing test** — `would_create_cycle`: A→B ok; then B→A detected; self-edge A→A rejected; add_edge persists valid edge.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement models + migration + cycle DFS in service.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): skill levels + acyclic prerequisite edges`.

### Task 12: Level/edge/override endpoints + copy-on-write read

**Files:**
- Modify: `backend/apps/skills/models.py` (`TenantSkillOverride`), `views.py`, `serializers.py`, `services.py`, migration
- Test: `backend/apps/skills/tests/test_overrides.py`, extend `test_levels_edges.py`

**Interfaces:**
- Produces:
  - `GET/PUT /skills/skills/{id}/levels/` (replace full 1..N rubric grid), `GET/POST/DELETE /skills/skills/{id}/edges/`, `POST /skills/skills/{id}/override/` — all `taxonomy.edit`, audited.
  - `TenantSkillOverride(TenantScopedModel)` — `skill FK`, `name (blank)`, `status (blank)`, `hidden Boolean default False`. `UNIQUE(tenant, skill)`.
  - `services.resolve_skill_view(queryset, tenant_id)` applies overrides (rename/hide) to global+tenant skills (copy-on-write; global untouched). Wire into Task 4's read queryset.

- [ ] **Step 1: Failing test** — PUT levels sets rubric grid; override renaming a global skill changes that tenant's read only (other tenant still sees global name); `hidden=True` removes it from that tenant's list; edges endpoint rejects a cycle (400).
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement override model/migration, endpoints, `resolve_skill_view`, wire into read.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): level/edge/override editors with copy-on-write reads`.

### Task 13: SkillAssertion (verified tier) + record endpoint

**Files:**
- Modify: `backend/apps/skills/models.py`, `serializers.py`, `views.py`, `urls.py`, migration
- Test: `backend/apps/skills/tests/test_assertions.py`

**Interfaces:**
- Produces: `SkillAssertion(TenantScopedModel)` — `membership FK`, `skill FK`, `level SmallInteger`, `skill_level FK(SkillLevel, null)`, `skill_version SmallInteger`, `verified_by FK(identity.Person, null)`, `verified_at DateTime`, `note (blank)`. Endpoints `GET/POST /skills/assertions/` (`skill.verify`), audited, idempotent create. POST records a verified level and (Task 16) triggers readiness recompute. **This is the only readiness source.**

- [ ] **Step 1: Failing test** — record an assertion as `skill.verify` holder → 201 pinning `skill_version`; non-holder → 403; list isolation (tenant A only); `verified_at` set.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement model/migration/endpoints/audit/idempotency.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): verified-tier SkillAssertion + record endpoint`.

### Task 14: Skill & profile versioning/publish

**Files:**
- Modify: `backend/apps/skills/services.py`, `views.py` (publish action); profiles added in Task 17 get the same
- Test: `backend/apps/skills/tests/test_versioning.py`

**Interfaces:**
- Produces: `services.publish_skill(skill, actor)` — transitions draft→published; editing a published skill's definition/levels creates a new `version` row (immutable prior retained), returns the new draft. `POST /skills/skills/{id}/publish/` (`taxonomy.edit`). Existing assertions keep pointing at their version.

- [ ] **Step 1: Failing test** — publish sets status published; editing published creates version 2 (version 1 row still exists, unchanged); assertion made against v1 still references v1.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement versioning service + publish endpoint.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(skills): skill versioning and publish flow`.

### Task 15: Profiles models (Track, JobProfile, ProfileRequirement, ReadinessSnapshot)

**Files:**
- Modify: `backend/apps/profiles/models.py`, create `backend/apps/profiles/migrations/0001_initial.py`
- Test: `backend/apps/profiles/tests/test_models.py`

**Interfaces:**
- Produces (all `TenantScopedModel` unless noted):
  - `Track` — `name`.
  - `JobProfile` — `track FK`, `grade SmallInteger`, `title`, `status` {draft,published,retired} default draft, `version SmallInteger default 1`.
  - `ProfileRequirement` — `job_profile FK`, `skill FK`, `min_level SmallInteger`, `criticality` {core,supporting,optional}. `UNIQUE(job_profile, skill)`.
  - `ReadinessSnapshot` — `membership FK`, `job_profile FK`, `met SmallInteger`, `total SmallInteger`, `blocking_skill_ids ArrayField(UUIDField)`, `job_profile_version SmallInteger`, `computed_at DateTime`. `UNIQUE(membership, job_profile)`.

- [ ] **Step 1: Failing test** — create track→profile→requirement; defaults; `UNIQUE` constraints.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement models + migration.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(profiles): track, job profile, requirement, readiness models`.

### Task 16: Readiness engine (service) + recompute hook & command

**Files:**
- Create: `backend/apps/profiles/services.py`, `backend/apps/profiles/management/commands/recompute_readiness.py`
- Modify: `backend/apps/skills/views.py` (assertion write → recompute hook)
- Test: `backend/apps/profiles/tests/test_readiness_service.py`

**Interfaces:**
- Produces: `services.compute_readiness(membership, job_profile) -> ReadinessSnapshot` — for each **core** requirement, met iff a `SkillAssertion` for that membership+skill has `level >= min_level`; `met/total` over core; `blocking_skill_ids` = unmet core skills; supporting/optional computed but advisory (not in met/total). Persists/updates the snapshot pinning `job_profile_version`. `services.recompute_for_membership(membership)` loops that membership's target profiles. Called on assertion create/update/delete. Command recomputes all (optionally `--tenant`).

- [ ] **Step 1: Failing test** — profile with 2 core + 1 supporting reqs; assertions meeting 1 core → `met=1,total=2`, blocking has the other core skill; raising the missing assertion → `met=2`, blocking empty; supporting never changes met/total; missing-assertion requirement does not raise.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement service + command + wire hook on assertion writes.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(profiles): readiness computation service + recompute command`.

### Task 17: Profiles CRUD + publish endpoints

**Files:**
- Create: `backend/apps/profiles/serializers.py`, `backend/apps/profiles/views.py`, `backend/apps/profiles/urls.py`; enable in `config/urls.py`
- Test: `backend/apps/profiles/tests/test_profiles_api.py`

**Interfaces:**
- Produces: `/api/profiles/tracks/` CRUD; `/api/profiles/job-profiles/` CRUD + nested `/requirements/` + `POST /{id}/publish/` (versioning like Task 14). All `jobprofile.edit`, audited, idempotent, tenant-scoped + isolation-tested; `@extend_schema(tags=["Profiles"])`.

- [ ] **Step 1: Failing test** — create track+profile+requirement as admin; isolation (A can't see B's profiles); non-admin write → 403; publish bumps status; editing published → new version.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement serializers/views/urls/schema/audit/idempotency.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(profiles): track/job-profile CRUD + publish`.

### Task 18: Readiness/gap + team + heatmap endpoints

**Files:**
- Modify: `backend/apps/profiles/views.py`, `serializers.py`, `urls.py`
- Test: `backend/apps/profiles/tests/test_readiness_api.py`

**Interfaces:**
- Produces:
  - `GET /api/profiles/me/readiness/?target=<profile>` (`skill.claim.submit`) — caller's gap: per-requirement met/needed, overall %, sorted closest-to-done.
  - `GET /api/profiles/readiness/?job_profile=` (`report.org.view`, subtree-scoped) — team snapshots.
  - `GET /api/profiles/heatmap/?org_unit=&job_profile=` (`report.org.view`) — members × core requirements grid, each cell met/unmet.
  - Reads come from `ReadinessSnapshot` (compute on demand if stale/missing).

- [ ] **Step 1: Failing test** — seed assertions → `me/readiness` returns correct % and ordering; team endpoint lists subtree members only, scoped to tenant A; missing `report.org.view` → 403; heatmap shape is members × core reqs.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement endpoints + serializers + schema.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(profiles): learner gap, team readiness, and heatmap endpoints`.

### Task 19: Isolation scan command + full isolation sweep

**Files:**
- Create: `backend/core/management/commands/scan_isolation.py`
- Test: `backend/core/tests/test_isolation_scan.py`, extend per-endpoint isolation tests if gaps found

**Interfaces:**
- Produces: `manage.py scan_isolation` iterates every `TenantScopedModel` subclass; under tenant A's context asserts no row with `tenant_id != A` is reachable via `Model.objects`; prints a report; exits non-zero on any leak. Test seeds two tenants across all new tables and asserts the scan passes (and fails if scoping is bypassed).

- [ ] **Step 1: Failing test** — seed both tenants across skills+profiles tables; run scan programmatically → clean; monkeypatch one model to use `all_tenants` → scan flags it.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Implement command (discover subclasses via `apps.get_models`), test.
- [ ] **Step 4:** tests → PASS.
- [ ] **Step 5:** Commit `feat(core): cross-tenant isolation scan command`.

### Task 20: Seed the demo ladder + final Swagger/lint pass

**Files:**
- Modify: `backend/apps/identity/management/commands/seed_demo.py`
- Test: `backend/apps/identity/tests/test_seed.py` (extend), `backend/core/tests/test_schema.py` (extend)

**Interfaces:**
- Produces: seed a Data Engineer track with L1/L2/L3 job profiles; skills (SQL, Python, Data modeling, Airflow, dbt, Kafka) with levels; profile requirements; and **verified assertions** for a demo learner (e.g. Priya) so `me/readiness` ≈ the screenshot (68%). All view actions carry `@extend_schema`; `make lint-backend` clean.

- [ ] **Step 1: Failing test** — after `seed_demo`, the demo learner's readiness snapshot for L2 has the expected met/total; schema test lists all Part B paths with tags.
- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3:** Extend seed; finish annotations.
- [ ] **Step 4:** `make test-backend` + `make lint-backend` → all PASS/clean. Run `scan_isolation` + `recompute_readiness` manually → clean.
- [ ] **Step 5:** Commit `chore(backend): demo ladder seed + final Swagger + lint pass`.

---

## Done when

- `make test-backend` green (isolation + negative-permission tests for every endpoint; readiness, versioning, cycle, import, idempotency units).
- `make lint-backend` clean.
- `/api/schema/swagger-ui/` documents every endpoint with tags/summaries/examples.
- `seed_demo` renders the gap/heatmap truthfully; `scan_isolation` reports no leaks.
