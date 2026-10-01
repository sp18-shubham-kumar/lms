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
