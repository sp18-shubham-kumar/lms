import pytest
from django.core.management import call_command


@pytest.mark.django_db
def test_seed_demo_is_idempotent_and_creates_two_tenants():
    from apps.identity.models import Membership, Tenant

    call_command("seed_demo")
    call_command("seed_demo")  # second run must not duplicate
    assert Tenant.objects.count() == 2
    # The shared person has a membership in both tenants.
    from django.contrib.auth import get_user_model

    Person = get_user_model()
    shared = Person.objects.get(email="dana@shared.test")
    assert Membership.all_tenants.filter(person=shared).count() == 2


@pytest.mark.django_db
def test_seed_demo_reconciles_capabilities_and_role_grants():
    from apps.authz.models import Capability, Role, RoleCapability
    from apps.identity.models import Tenant
    from core.context import tenant_context

    call_command("seed_demo")

    required = {
        "directory.view",
        "skill.claim.submit",
        "taxonomy.edit",
        "jobprofile.edit",
        "member.invite",
        "member.offboard",
        "skill.verify",
        "report.org.view",
    }
    existing = set(Capability.objects.values_list("key", flat=True))
    assert required <= existing  # every required capability exists

    acme = Tenant.objects.get(slug="acme")
    with tenant_context(acme.id):

        def caps_for(role_name: str) -> set[str]:
            role = Role.objects.get(tenant=acme, name=role_name)
            return set(
                RoleCapability.objects.filter(role=role).values_list("capability__key", flat=True)
            )

        learner = caps_for("Learner")
        manager = caps_for("Manager")
        admin = caps_for("Admin")

        assert {"directory.view", "skill.claim.submit"} <= learner
        assert "report.org.view" in manager
        assert required <= admin  # admin holds every required capability


@pytest.mark.django_db
def test_seed_demo_seeds_global_skill_domains_and_skills():
    from apps.skills.models import Skill, SkillDomain

    call_command("seed_demo")
    call_command("seed_demo")  # idempotent

    # Global domains/skills (tenant NULL) are seeded for everyone.
    assert SkillDomain.objects.filter(tenant__isnull=True).exists()
    assert Skill.objects.filter(tenant__isnull=True).exists()


@pytest.mark.django_db
def test_seed_demo_creates_data_engineer_ladder():
    """
    After seed_demo, the Data Engineering track with L1/L2/L3 job profiles must exist,
    skill levels for core skills must be seeded, bob's verified assertions must exist,
    and his readiness snapshot for L2 must have met=2 and total=3.
    """
    from apps.identity.models import Membership, Tenant
    from apps.profiles.models import JobProfile, ReadinessSnapshot, Track
    from apps.skills.models import Skill, SkillAssertion, SkillLevel
    from core.context import tenant_context

    call_command("seed_demo")
    call_command("seed_demo")  # idempotent

    acme = Tenant.objects.get(slug="acme")

    with tenant_context(acme.id):
        # Track exists.
        track = Track.objects.filter(name="Data Engineering").first()
        assert track is not None, "Data Engineering track must be seeded"

        # Three job profiles for the Data Engineering track.
        profiles = list(JobProfile.objects.filter(track=track).order_by("grade"))
        assert len(profiles) >= 3, f"Expected at least 3 profiles, got {len(profiles)}"
        grades = [p.grade for p in profiles]
        assert 1 in grades and 2 in grades and 3 in grades

        # Skill levels are seeded (at least one SkillLevel for SQL, Python, Data modeling).
        sql_skill = Skill.objects.filter(slug="sql").first()
        assert sql_skill is not None, "SQL skill must be seeded"
        assert SkillLevel.objects.filter(skill=sql_skill).exists(), "SQL SkillLevels must be seeded"

        python_skill = Skill.objects.filter(slug="python").first()
        assert python_skill is not None
        assert SkillLevel.objects.filter(skill=python_skill).exists()

        # Bob's assertions.
        import django.contrib.auth

        User = django.contrib.auth.get_user_model()
        bob = User.objects.get(email="bob@acme.test")
        bob_membership = Membership.objects.get(person=bob, tenant=acme)

        # Bob should have at least 3 verified assertions (SQL, Python, Data modeling).
        bob_assertions = SkillAssertion.objects.filter(membership=bob_membership)
        assert (
            bob_assertions.count() >= 3
        ), f"Bob should have >= 3 assertions, got {bob_assertions.count()}"

        # Readiness snapshot for bob against L2 profile.
        l2_profile = JobProfile.objects.filter(track=track, grade=2).first()
        assert l2_profile is not None

        snapshot = ReadinessSnapshot.objects.filter(
            membership=bob_membership, job_profile=l2_profile
        ).first()
        assert snapshot is not None, "Readiness snapshot for bob x L2 must exist"
        assert snapshot.met == 2, f"Expected met=2, got {snapshot.met}"
        assert snapshot.total == 3, f"Expected total=3, got {snapshot.total}"
