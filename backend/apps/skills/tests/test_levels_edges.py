import pytest


def _global_domain():
    from apps.skills.models import SkillDomain

    return SkillDomain.objects.create(tenant=None, name="Global")


def _skill(domain, name, slug):
    from apps.skills.models import Skill

    return Skill.objects.create(tenant=None, domain=domain, name=name, slug=slug)


@pytest.mark.django_db
def test_skill_level_defaults_and_uniqueness():
    from django.db import IntegrityError

    from apps.skills.models import SkillLevel

    gd = _global_domain()
    skill = _skill(gd, "SQL", "sql")
    level = SkillLevel.objects.create(
        skill=skill,
        level=1,
        title="Beginner",
        indicators=["writes SELECT"],
        evidence_kinds=["quiz"],
    )
    assert level.min_verifier_level is None
    assert level.validity_months is None
    assert level.indicators == ["writes SELECT"]
    assert str(level)

    with pytest.raises(IntegrityError):
        SkillLevel.objects.create(skill=skill, level=1, title="Dup")


@pytest.mark.django_db
def test_skill_level_validators_reject_out_of_range():
    from django.core.exceptions import ValidationError

    from apps.skills.models import SkillLevel

    gd = _global_domain()
    skill = _skill(gd, "SQL", "sql")
    level = SkillLevel(skill=skill, level=9, title="Too high")
    with pytest.raises(ValidationError):
        level.full_clean()


@pytest.mark.django_db
def test_would_create_cycle():
    from apps.skills import services

    gd = _global_domain()
    a = _skill(gd, "A", "a")
    b = _skill(gd, "B", "b")

    # No edges yet: adding A->B introduces no cycle.
    assert services.would_create_cycle(a.id, b.id) is False
    services.add_edge(a, b, "prerequisite")
    # Now B->A would close a cycle A->B->A.
    assert services.would_create_cycle(b.id, a.id) is True


@pytest.mark.django_db
def test_add_edge_rejects_self_edge():
    from django.core.exceptions import ValidationError

    from apps.skills import services

    gd = _global_domain()
    a = _skill(gd, "A", "a")
    with pytest.raises(ValidationError):
        services.add_edge(a, a, "prerequisite")


@pytest.mark.django_db
def test_add_edge_rejects_cycle():
    from django.core.exceptions import ValidationError

    from apps.skills import services

    gd = _global_domain()
    a = _skill(gd, "A", "a")
    b = _skill(gd, "B", "b")
    services.add_edge(a, b, "prerequisite")
    with pytest.raises(ValidationError):
        services.add_edge(b, a, "prerequisite")


@pytest.mark.django_db
def test_add_edge_persists_valid_edge_and_uniqueness():
    from django.db import IntegrityError

    from apps.skills import services
    from apps.skills.models import SkillEdge

    gd = _global_domain()
    a = _skill(gd, "A", "a")
    b = _skill(gd, "B", "b")
    edge = services.add_edge(a, b, "adjacent")
    assert SkillEdge.objects.filter(id=edge.id).exists()

    with pytest.raises(IntegrityError):
        SkillEdge.objects.create(from_skill=a, to_skill=b, kind="adjacent")
