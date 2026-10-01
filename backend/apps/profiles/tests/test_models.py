"""
Tests for Task 15: Track, JobProfile, ProfileRequirement, ReadinessSnapshot models.
Verifies defaults, relationships, and UNIQUE constraints.
"""

import pytest
from django.db import IntegrityError
from django.utils import timezone


def _seed_tenant(slug):
    from apps.identity.models import Tenant

    return Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")


def _seed_membership(tenant):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(
        email=f"user-{tenant.slug}@test.test", display_name="User", password="pw-12345"
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
    return membership


def _seed_skill(tenant):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name="Engineering")
        return Skill.objects.create(
            tenant=tenant, domain=domain, name="SQL", slug="sql", version=1
        )


@pytest.mark.django_db
def test_track_defaults():
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    assert track.name == "Backend"
    assert track.tenant_id == tenant.id
    assert str(track) == "Backend"


@pytest.mark.django_db
def test_job_profile_defaults():
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(
            tenant=tenant, track=track, grade=2, title="Software Engineer II"
        )

    assert profile.status == "draft"
    assert profile.version == 1
    assert profile.grade == 2
    assert profile.title == "Software Engineer II"
    assert str(profile) == "Software Engineer II (v1)"


@pytest.mark.django_db
def test_profile_requirement_unique_constraint():
    """Each (job_profile, skill) pair must be unique."""
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    skill = _seed_skill(tenant)
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(
            tenant=tenant, track=track, grade=1, title="L1"
        )
        ProfileRequirement.objects.create(
            tenant=tenant,
            job_profile=profile,
            skill=skill,
            min_level=2,
            criticality="core",
        )
        with pytest.raises(IntegrityError):
            ProfileRequirement.objects.create(
                tenant=tenant,
                job_profile=profile,
                skill=skill,
                min_level=3,
                criticality="supporting",
            )


@pytest.mark.django_db
def test_profile_requirement_criticality_choices():
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name="D")
        skill1 = Skill.objects.create(tenant=tenant, domain=domain, name="S1", slug="s1")
        skill2 = Skill.objects.create(tenant=tenant, domain=domain, name="S2", slug="s2")
        skill3 = Skill.objects.create(tenant=tenant, domain=domain, name="S3", slug="s3")
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="L1")
        req1 = ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=skill1, min_level=2, criticality="core"
        )
        req2 = ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=skill2, min_level=1, criticality="supporting"
        )
        req3 = ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=skill3, min_level=1, criticality="optional"
        )

    assert req1.criticality == "core"
    assert req2.criticality == "supporting"
    assert req3.criticality == "optional"


@pytest.mark.django_db
def test_readiness_snapshot_unique_constraint():
    """Each (membership, job_profile) pair must be unique."""
    from apps.profiles.models import JobProfile, ReadinessSnapshot, Track
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    membership = _seed_membership(tenant)
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="L1")
        now = timezone.now()
        ReadinessSnapshot.objects.create(
            tenant=tenant,
            membership=membership,
            job_profile=profile,
            met=1,
            total=2,
            blocking_skill_ids=[],
            job_profile_version=1,
            computed_at=now,
        )
        with pytest.raises(IntegrityError):
            ReadinessSnapshot.objects.create(
                tenant=tenant,
                membership=membership,
                job_profile=profile,
                met=2,
                total=2,
                blocking_skill_ids=[],
                job_profile_version=1,
                computed_at=now,
            )


@pytest.mark.django_db
def test_readiness_snapshot_str():
    from apps.profiles.models import JobProfile, ReadinessSnapshot, Track
    from core.context import tenant_context

    tenant = _seed_tenant("acme")
    membership = _seed_membership(tenant)
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="L1")
        snapshot = ReadinessSnapshot.objects.create(
            tenant=tenant,
            membership=membership,
            job_profile=profile,
            met=1,
            total=2,
            blocking_skill_ids=[],
            job_profile_version=1,
            computed_at=timezone.now(),
        )

    assert "1/2" in str(snapshot)
