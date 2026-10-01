import pytest


@pytest.mark.django_db
def test_global_and_tenant_skill_defaults():
    from apps.identity.models import Tenant
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    # Global domain + skill (tenant=None).
    global_domain = SkillDomain.objects.create(tenant=None, name="Engineering")
    global_skill = Skill.objects.create(tenant=None, domain=global_domain, name="SQL", slug="sql")
    assert global_skill.status == "draft"
    assert global_skill.version == 1
    assert global_skill.tenant_id is None
    assert global_domain.sort == 0
    assert str(global_skill) == "SQL"
    assert str(global_domain) == "Engineering"

    # Tenant-owned skill.
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    with tenant_context(tenant.id):
        tenant_domain = SkillDomain.objects.create(tenant=tenant, name="Data")
        tenant_skill = Skill.objects.create(
            tenant=tenant, domain=tenant_domain, name="dbt", slug="dbt"
        )
    assert tenant_skill.status == "draft"
    assert tenant_skill.version == 1
    assert tenant_skill.tenant_id == tenant.id


@pytest.mark.django_db
def test_skilldomain_visible_returns_globals_union_tenant():
    from apps.identity.models import Tenant
    from apps.skills.models import SkillDomain
    from core.context import tenant_context

    g = SkillDomain.objects.create(tenant=None, name="Global")
    a = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    b = Tenant.objects.create(slug="nw", name="Northwind", status="active", plan="pro")
    with tenant_context(a.id):
        da = SkillDomain.objects.create(tenant=a, name="A-only")
    with tenant_context(b.id):
        db = SkillDomain.objects.create(tenant=b, name="B-only")

    with tenant_context(a.id):
        visible_ids = set(SkillDomain.objects.visible().values_list("id", flat=True))
    assert g.id in visible_ids
    assert da.id in visible_ids
    assert db.id not in visible_ids


@pytest.mark.django_db
def test_skill_visible_returns_globals_union_tenant():
    from apps.identity.models import Tenant
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    gd = SkillDomain.objects.create(tenant=None, name="Global")
    gs = Skill.objects.create(tenant=None, domain=gd, name="SQL", slug="sql")
    a = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    b = Tenant.objects.create(slug="nw", name="Northwind", status="active", plan="pro")
    with tenant_context(a.id):
        sa = Skill.objects.create(tenant=a, domain=gd, name="A-skill", slug="a-skill")
    with tenant_context(b.id):
        sb = Skill.objects.create(tenant=b, domain=gd, name="B-skill", slug="b-skill")

    with tenant_context(a.id):
        visible_ids = set(Skill.objects.visible().values_list("id", flat=True))
    assert gs.id in visible_ids
    assert sa.id in visible_ids
    assert sb.id not in visible_ids
