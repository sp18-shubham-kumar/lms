"""
Authorization models (Phase 1).

Planned tables (see docs/specs/data-model.md and docs/specs/phase-1.md):
- Capability        — flat, seeded key list (not tenant-editable).
- Role / RoleCapability — named bundles of capabilities per tenant.
- RoleGrant         — grants a role to a principal (person|group) within a scope.
- VerifierAuthority — who may verify which skill, up to which level, for which
                      org subtree, within a validity window (Phase 2+ usage).

All rows except `Capability` inherit `core.models.TenantScopedModel`.
Authorization decisions funnel through `core.permissions.can()`.
"""

# Models land in Phase 1 — see docs/specs/phase-1.md.
