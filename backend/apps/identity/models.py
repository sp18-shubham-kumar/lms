"""
Identity & tenancy models (Phase 1).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-1.md):
- Tenant        — the organisation boundary (slug, name, status, plan, theming).
- Person        — global identity, not owned by a tenant (email UNIQUE).
- OrgUnit       — tenant org hierarchy (materialised path for subtree scope).
- Membership    — links a Person to a Tenant (role, org unit, grade); one per pair.
- IdentityProvider — per-tenant OIDC config.

Conventions:
- `Tenant` and `Person` are NOT tenant-scoped (they define/cross the boundary),
  so they inherit `core.models.UUIDModel` + `TimeStampedModel` directly.
- Every other model here inherits `core.models.TenantScopedModel`.
"""

# Models land in Phase 1 — see docs/specs/phase-1.md.
