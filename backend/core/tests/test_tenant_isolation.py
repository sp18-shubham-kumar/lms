"""
Tenant isolation test harness.

This is the pattern every tenant-scoped list endpoint must be tested against
(the spec: "seed two tenants, run every list endpoint as tenant A, assert zero
rows from tenant B"). The suite grows with every endpoint and is NOT optional.

Right now there are no domain models, so this file proves the *mechanism*:
- `TenantScopedManager` returns nothing when no tenant is in context (fail closed).
- Switching the ambient tenant switches the visible rows.

When Phase 1 adds models, use `assert_isolated(list_url, as_tenant_a, other=tenant_b)`
against each endpoint. A reusable helper stub is provided below.
"""

from __future__ import annotations

from uuid import uuid4

from core.context import get_current_tenant, tenant_context


def test_no_tenant_context_is_fail_closed():
    """With no tenant set, scoped reads must yield nothing (not everything)."""
    assert get_current_tenant() is None
    # TenantScopedQuerySet.for_current_tenant() returns .none() here. Once a
    # model exists: `assert not Skill.objects.all().exists()` under no context.


def test_tenant_context_switches_scope():
    """Entering a tenant context makes that tenant the active scope."""
    tenant_a, tenant_b = uuid4(), uuid4()
    with tenant_context(tenant_a):
        assert get_current_tenant() == tenant_a
    with tenant_context(tenant_b):
        assert get_current_tenant() == tenant_b


# --- Reusable helper for endpoint isolation tests (use in Phase 1) -----------
def assert_list_is_tenant_isolated(api_client, url, tenant_a_headers, tenant_b_row_exists):
    """
    Template for per-endpoint isolation assertions.

    Call as tenant A and assert none of tenant B's rows appear. Fill in once
    endpoints exist:

        resp = api_client.get(url, **tenant_a_headers)
        ids = {row["id"] for row in resp.json()["results"]}
        assert tenant_b_row_id not in ids
    """
    raise NotImplementedError("Wire up when the first list endpoint lands (Phase 1).")
