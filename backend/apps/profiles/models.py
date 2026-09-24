"""
Job profiles & readiness models (Phase 2).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-2.md):
- Track             — e.g. Backend, Design, Sales.
- JobProfile        — track + grade + title (versioned/publishable).
- ProfileRequirement — required skill level per profile (core|supporting|optional).
- ReadinessSnapshot — cached met/total + blocking skills per membership/profile.

Readiness is computed (count verified assertions meeting each requirement),
never asserted. All rows inherit `core.models.TenantScopedModel`.
"""

# Models land in Phase 2 — see docs/specs/phase-2.md.
