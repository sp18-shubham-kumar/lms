"""
Skill taxonomy models (Phase 1 CRUD, Phase 2 framework).

Planned tables (see docs/specs/data-model.md, phase-1.md, phase-2.md):
- SkillDomain   — grouping (tenant_id NULL = global).
- Skill         — a capability; versioned, never mutated in place; retire, don't delete.
- SelfDeclaredSkill (Phase 1) — a member's self-claim (the untrusted tier).
- SkillLevel    (Phase 2) — 1..5 with indicators, evidence kinds, min verifier level.
- SkillEdge     (Phase 2) — prerequisite/adjacent graph; must stay acyclic.
- TenantSkillOverride (Phase 2) — copy-on-write per-tenant customisation.

Global rows use `tenant_id IS NULL`; tenant rows inherit `TenantScopedModel`.
Keep self-declared (Phase 1) and verified assertions (later) as separate records.
"""

# Phase 1: Skill + SelfDeclaredSkill CRUD. See docs/specs/phase-1.md.
