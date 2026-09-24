# Build order

> The full MVP spec sequences work into five stages. Each makes the next one
> demonstrable to a pilot. **Phase 1 = Spine; Phase 2 = Map.** Stages 3–5 are the
> longer-term product beyond the current two-phase scope, kept here for context.

| Stage | Ships | Provable claim | Scope |
| --- | --- | --- | --- |
| **1. Spine** | Tenancy + identity, authorization, audit log, isolation test suite | Two orgs coexist, nobody sees across | **Phase 1** |
| **2. Map** | Taxonomy with rubrics, job profiles + readiness diff, admin editors | An org describes its own framework without us | **Phase 2** |
| 3. Loop | Verification end-to-end, basic assessment, resource pointers, roadmaps | Claim → verify → gap closes (the product) | Future |
| 4. Proof | Credentials with signing, public verify page, expiry/recert | A credential holds up outside the org | Future |
| 5. Motion | Rewards ledger, automation, reports | The loop runs without an admin pushing it | Future |

Stage 3 (verification) is the differentiator and the one stage that cannot be cut down.
Under time pressure, ship a smaller taxonomy / fewer reports / no rewards — never a
weaker verification workflow.

## Suggested Jira epics

- **P1 — Foundation**: identity, tenancy, authorization, skills, directory, admin, audit, QA.
- **P2 — Skill Framework**: levels, rubrics, prerequisites, profiles, readiness, heatmap, versioning, QA.
- **Platform**: CI/CD, environments, database migrations, observability.
- **Demo & Documentation**: seed data, architecture diagram, demo script, known gaps.

## Cross-team responsibilities

| Workstream | Responsibilities |
| --- | --- |
| Backend | Schema, APIs, business rules, authorization, migrations, tests |
| Frontend | Dashboard, directory, skill/profile admin, gap/heatmap screens |
| QA | Test cases, isolation tests, permission matrix, regression testing |
| DevOps/Platform | CI/CD, staging, env vars/secrets, deployment |
| Product/Coordinator | Requirements, demo flow, seed data, acceptance criteria |
