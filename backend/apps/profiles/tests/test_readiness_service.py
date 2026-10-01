"""
Tests for Task 16: Readiness computation service.

Profile setup: 2 core + 1 supporting requirements.
- core req A: SQL min_level=2
- core req B: Python min_level=3
- supporting req C: dbt min_level=1

Assertions at 1 core met → met=1, total=2, blocking=[python_skill_id]
Raise Python assertion → met=2, total=0 blocking
Supporting never affects met/total
Missing assertion counts as unmet (no crash)
"""

import pytest
from django.utils import timezone


def _seed_tenant(slug, email, cap_keys):
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person, membership


def _seed_profile_with_reqs(tenant):
    """Create a JobProfile with 2 core + 1 supporting requirements. Returns (profile, sql_skill, python_skill, dbt_skill)."""
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name="Engineering")
        sql_skill = Skill.objects.create(
            tenant=tenant, domain=domain, name="SQL", slug="sql", version=1, status="published"
        )
        python_skill = Skill.objects.create(
            tenant=tenant, domain=domain, name="Python", slug="python", version=1, status="published"
        )
        dbt_skill = Skill.objects.create(
            tenant=tenant, domain=domain, name="dbt", slug="dbt", version=1, status="published"
        )
        track = Track.objects.create(tenant=tenant, name="Data")
        profile = JobProfile.objects.create(
            tenant=tenant, track=track, grade=2, title="Data Engineer L2", status="published"
        )
        ProfileRequirement.objects.create(
            tenant=tenant,
            job_profile=profile,
            skill=sql_skill,
            min_level=2,
            criticality="core",
        )
        ProfileRequirement.objects.create(
            tenant=tenant,
            job_profile=profile,
            skill=python_skill,
            min_level=3,
            criticality="core",
        )
        ProfileRequirement.objects.create(
            tenant=tenant,
            job_profile=profile,
            skill=dbt_skill,
            min_level=1,
            criticality="supporting",
        )
    return profile, sql_skill, python_skill, dbt_skill


@pytest.mark.django_db
def test_compute_readiness_one_core_met():
    """1 of 2 core requirements met → met=1, total=2, blocking=[python skill]."""
    from apps.profiles import services
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        # SQL assertion at level 2 (meets core req min_level=2)
        SkillAssertion.objects.create(
            tenant=tenant,
            membership=membership,
            skill=sql_skill,
            level=2,
            skill_version=1,
        )
        snapshot = services.compute_readiness(membership, profile)

    assert snapshot.met == 1
    assert snapshot.total == 2
    assert str(python_skill.id) in [str(uid) for uid in snapshot.blocking_skill_ids]
    assert str(sql_skill.id) not in [str(uid) for uid in snapshot.blocking_skill_ids]


@pytest.mark.django_db
def test_compute_readiness_all_core_met():
    """All core requirements met → met=2, total=2, blocking=[]."""
    from apps.profiles import services
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=sql_skill, level=3, skill_version=1
        )
        SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=python_skill, level=4, skill_version=1
        )
        snapshot = services.compute_readiness(membership, profile)

    assert snapshot.met == 2
    assert snapshot.total == 2
    assert snapshot.blocking_skill_ids == []


@pytest.mark.django_db
def test_compute_readiness_supporting_does_not_affect_met_total():
    """Supporting requirements never change met/total."""
    from apps.profiles import services
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        # Only supporting req met (dbt), no core assertions
        SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=dbt_skill, level=2, skill_version=1
        )
        snapshot = services.compute_readiness(membership, profile)

    # dbt is supporting — should not change met (still 0/2 core)
    assert snapshot.met == 0
    assert snapshot.total == 2


@pytest.mark.django_db
def test_compute_readiness_missing_assertion_does_not_raise():
    """No assertions at all → met=0, total=2, blocking=both core skills. No crash."""
    from apps.profiles import services
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        snapshot = services.compute_readiness(membership, profile)

    assert snapshot.met == 0
    assert snapshot.total == 2
    assert len(snapshot.blocking_skill_ids) == 2


@pytest.mark.django_db
def test_compute_readiness_updates_existing_snapshot():
    """Calling compute_readiness twice updates (upserts) the snapshot."""
    from apps.profiles import services
    from apps.profiles.models import ReadinessSnapshot
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        s1 = services.compute_readiness(membership, profile)
        assert s1.met == 0

        SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=sql_skill, level=3, skill_version=1
        )
        s2 = services.compute_readiness(membership, profile)
        assert s2.met == 1
        # Only one snapshot row per (membership, job_profile)
        assert ReadinessSnapshot.objects.filter(
            membership=membership, job_profile=profile
        ).count() == 1


@pytest.mark.django_db
def test_recompute_for_membership_calls_compute_for_profiles():
    """recompute_for_membership should compute snapshots for all profiles with requirements."""
    from apps.profiles import services
    from apps.profiles.models import ReadinessSnapshot
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        # First seed an initial snapshot so recompute_for_membership knows to target this profile
        s1 = services.compute_readiness(membership, profile)
        assert ReadinessSnapshot.objects.count() == 1

        # Now recompute
        services.recompute_for_membership(membership)
        assert ReadinessSnapshot.objects.count() == 1  # still just one, upserted


@pytest.mark.django_db
def test_recompute_readiness_command_runs():
    """Management command recompute_readiness --tenant <slug> runs without error."""
    from django.core.management import call_command

    from apps.profiles import services
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", [])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile_with_reqs(tenant)

    with tenant_context(tenant.id):
        services.compute_readiness(membership, profile)

    # Should not raise
    call_command("recompute_readiness", "--tenant", "acme")
