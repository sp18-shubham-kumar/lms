# Phase 2 — Skill Framework

> Source: `docs/Skills_LMS_Requirements_Tasks_Subtasks.docx` §4–5.
> Goal: an organisation can describe its own skill framework and grades, and a learner
> can see the gap between where they are and a target grade. The "Map" stage of the
> [roadmap](./roadmap.md).

## Requirements

| ID | Requirement | Owner |
| --- | --- | --- |
| P2-R1 | Define skill levels and level rubrics | Product/Backend |
| P2-R2 | Add skill prerequisite relationships | Backend |
| P2-R3 | Allow organization-specific skill customization | Backend |
| P2-R4 | Create tracks and job grades | Backend + Frontend |
| P2-R5 | Define skill requirements per job profile | Backend + Frontend |
| P2-R6 | Calculate learner readiness/gaps against a target profile | Backend |
| P2-R7 | Show individual gap view | Frontend |
| P2-R8 | Show manager/team skill heatmap | Frontend + Backend |
| P2-R9 | Version/publish skill and profile changes | Backend |
| P2-R10 | Add tests for readiness and versioning | QA + Backend |

## Subtasks

**Model**
- Define the level model and rubric format; seed example levels.
- Create the prerequisite / skill-edge model (must stay acyclic — reject cycles on insert).
- Implement skill versioning and a publish flow.
- Implement tenant-specific skill overrides (copy-on-write).
- Create track / job-profile / requirement models.

**API**
- Build job-profile CRUD APIs.
- Implement the readiness calculation service.
- Implement the gap API for a learner + target grade.

**Frontend**
- Admin UI for skill levels and rubrics (spreadsheet-style grid, live diff, publish step).
- Admin UI for tracks and job grades.
- Profile requirement editor.
- Learner gap/readiness screen (home screen = the gap diff, sorted "closest to done").
- Manager team heatmap (subtree members × core requirements; filter "one gap from promotion").

**Quality**
- Unit tests for readiness calculations.
- Tests for profile/skill version behaviour.
- Seed a realistic demo career ladder, e.g. Data Engineer L1/L2/L3.

## Key rules (from the spec)

- Readiness is **computed** (count verified assertions meeting each requirement), cached
  in `readiness_snapshot`, recomputed on verified-assertion writes + nightly.
- Core requirements gate promotion; supporting are advisory.
- Promotion is not automated — platform says "requirements met", an admin records it.
- Rubric text is the primary content of a skill page — one source, read by both learners
  (to aim) and verifiers (to sign off).

## Provable claim at the end

> An organisation can describe its own skill framework and grades without our help, and
> a learner/manager can see exactly which verified skills are missing for a target grade.
