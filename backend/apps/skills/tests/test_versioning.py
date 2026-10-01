import pytest
from rest_framework.test import APIClient


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


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


def _tenant_skill(tenant, slug="sql"):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        gd = SkillDomain.objects.create(tenant=tenant, name="D")
        return Skill.objects.create(tenant=tenant, domain=gd, name="SQL", slug=slug)


@pytest.mark.django_db
def test_publish_skill_sets_status_published():
    from apps.skills import services
    from apps.skills.models import Skill
    from core.context import tenant_context

    tenant, person, _ = _seed_tenant("acme", "a@acme.test", ["taxonomy.edit"])
    skill = _tenant_skill(tenant)
    assert skill.status == "draft"
    with tenant_context(tenant.id):
        published = services.publish_skill(skill, person)
    assert published.status == "published"
    with tenant_context(tenant.id):
        assert Skill.objects.get(id=skill.id).status == "published"


@pytest.mark.django_db
def test_editing_published_skill_creates_new_version():
    from apps.skills import services
    from apps.skills.models import Skill
    from core.context import tenant_context

    tenant, person, _ = _seed_tenant("acme", "a@acme.test", ["taxonomy.edit"])
    skill = _tenant_skill(tenant)
    with tenant_context(tenant.id):
        services.publish_skill(skill, person)
        new_draft = services.new_version_from(skill, person)

    assert new_draft.id != skill.id
    assert new_draft.version == 2
    assert new_draft.status == "draft"

    with tenant_context(tenant.id):
        # Version 1 row still exists, unchanged (immutable prior).
        v1 = Skill.objects.get(id=skill.id)
        assert v1.version == 1
        assert v1.status == "published"
        assert Skill.objects.filter(slug=skill.slug).count() == 2


@pytest.mark.django_db
def test_assertion_against_v1_still_references_v1():
    from apps.skills import services
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["taxonomy.edit"])
    skill = _tenant_skill(tenant)
    with tenant_context(tenant.id):
        services.publish_skill(skill, person)
        assertion = SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=skill, level=2, skill_version=skill.version
        )
        services.new_version_from(skill, person)
        assertion.refresh_from_db()

    assert assertion.skill_id == skill.id
    assert assertion.skill_version == 1


@pytest.mark.django_db
def test_publish_endpoint():
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["taxonomy.edit"])
    skill = _tenant_skill(tenant)
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        f"/api/skills/{skill.id}/publish/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert AuditLog.objects.filter(action="skill.publish").exists()


@pytest.mark.django_db
def test_publish_endpoint_denied_without_taxonomy_edit():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    skill = _tenant_skill(tenant)
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        f"/api/skills/{skill.id}/publish/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403
