"""
Tests for the cross-tenant isolation scan management command.

The scan discovers every TenantScopedModel subclass and, under each tenant's
context, checks that Model.objects.all() returns ONLY that tenant's rows.
A clean scan exits 0; any leak exits 1.
"""

from __future__ import annotations

from io import StringIO
from unittest import mock

import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_scan_isolation_passes_on_clean_data():
    """
    After seeding two tenants across skills + profiles tables, the scan should
    report no leaks and return normally (no sys.exit(1)).
    """
    from apps.authz.models import Role
    from apps.identity.models import Tenant
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from apps.skills.models import Skill as SkillModel
    from apps.skills.models import SkillDomain, TenantSkillOverride
    from core.context import tenant_context

    # Create two tenants.
    tenant_a = Tenant.objects.create(
        slug="scan-a", name="Scan A", status="active", plan="pro", accent_color="#aaa"
    )
    tenant_b = Tenant.objects.create(
        slug="scan-b", name="Scan B", status="active", plan="pro", accent_color="#bbb"
    )

    # Each tenant gets a Role.
    with tenant_context(tenant_a.id):
        Role.objects.create(tenant=tenant_a, name="Admin", is_system=True)
    with tenant_context(tenant_b.id):
        Role.objects.create(tenant=tenant_b, name="Admin", is_system=True)

    # Global skill domain + skill (tenant=None, not scoped).
    domain = SkillDomain.objects.create(tenant=None, name="Scan Domain")
    skill = SkillModel.objects.create(
        tenant=None,
        domain=domain,
        name="Scan Skill",
        slug="scan-skill",
        status="published",
        version=1,
    )

    # TenantSkillOverride, Track, and JobProfile for each tenant.
    with tenant_context(tenant_a.id):
        TenantSkillOverride.objects.create(tenant=tenant_a, skill=skill, name="Override A")
        track_a = Track.objects.create(tenant=tenant_a, name="Track A")
        profile_a = JobProfile.objects.create(
            tenant=tenant_a, track=track_a, grade=1, title="L1 A", version=1
        )
        ProfileRequirement.objects.create(
            tenant=tenant_a,
            job_profile=profile_a,
            skill=skill,
            min_level=1,
            criticality="core",
        )

    with tenant_context(tenant_b.id):
        TenantSkillOverride.objects.create(tenant=tenant_b, skill=skill, name="Override B")
        track_b = Track.objects.create(tenant=tenant_b, name="Track B")
        profile_b = JobProfile.objects.create(
            tenant=tenant_b, track=track_b, grade=1, title="L1 B", version=1
        )
        ProfileRequirement.objects.create(
            tenant=tenant_b,
            job_profile=profile_b,
            skill=skill,
            min_level=1,
            criticality="core",
        )

    # Run the scan — should succeed with no leaks.
    out = StringIO()
    # scan_isolation should NOT call sys.exit(1) when no leaks exist.
    call_command("scan_isolation", stdout=out)
    output = out.getvalue()
    assert "PASS" in output or "No leaks" in output or "OK" in output or "clean" in output.lower()


@pytest.mark.django_db
def test_scan_isolation_exits_nonzero_on_leak():
    """
    If the scan detects rows from another tenant reachable under the wrong
    tenant context (i.e., the manager scoping is bypassed), it exits non-zero.

    We simulate the leak by monkey-patching the scan's internal check function
    to return a fake leak result, then verify sys.exit(1) is raised.

    We also need at least one tenant-scoped row so that _discover_models finds
    tenant_ids to iterate (otherwise check_model_for_leak is never called).
    """
    from apps.authz.models import Role
    from apps.identity.models import Tenant
    from core.context import tenant_context
    from core.management.commands.scan_isolation import Command

    tenant = Tenant.objects.create(
        slug="scan-leak", name="Scan Leak", status="active", plan="pro", accent_color="#ccc"
    )
    with tenant_context(tenant.id):
        Role.objects.create(tenant=tenant, name="Admin", is_system=True)

    # Patch check_model_for_leak to simulate a leak on the first call.
    call_count = {"n": 0}

    def fake_leak_checker(model_class: type, tenant_id: object) -> list[str]:
        call_count["n"] += 1
        if call_count["n"] == 1:
            return [f"LEAK: {model_class.__name__} tenant_id={tenant_id} has cross-tenant rows"]
        return []

    with mock.patch.object(Command, "check_model_for_leak", side_effect=fake_leak_checker):
        with pytest.raises(SystemExit) as exc_info:
            call_command("scan_isolation")
    assert exc_info.value.code == 1
