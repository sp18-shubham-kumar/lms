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


def _tenant_skill(tenant, slug="sql", version=1):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        gd = SkillDomain.objects.create(tenant=tenant, name="D")
        return Skill.objects.create(
            tenant=tenant, domain=gd, name=slug.upper(), slug=slug, version=version
        )


@pytest.mark.django_db
def test_record_assertion_pins_skill_version():
    from core.models import AuditLog

    tenant, _, membership = _seed_tenant("acme", "a@acme.test", ["skill.verify"])
    skill = _tenant_skill(tenant, version=3)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/assertions/",
        {"membership": str(membership.id), "skill": str(skill.id), "level": 2},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["skill_version"] == 3
    assert body["verified_at"] is not None
    assert AuditLog.objects.filter(action="skill.assertion.record").exists()


@pytest.mark.django_db
def test_record_assertion_denied_without_skill_verify():
    tenant, _, membership = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    skill = _tenant_skill(tenant)
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/assertions/",
        {"membership": str(membership.id), "skill": str(skill.id), "level": 2},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_assertions_list_is_tenant_isolated():
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant_a, _, mem_a = _seed_tenant("acme", "a@acme.test", ["skill.verify"])
    tenant_b, _, mem_b = _seed_tenant("northwind", "b@nw.test", ["skill.verify"])
    skill_a = _tenant_skill(tenant_a, slug="a-sql")
    skill_b = _tenant_skill(tenant_b, slug="b-sql")

    with tenant_context(tenant_a.id):
        a_assertion = SkillAssertion.objects.create(
            tenant=tenant_a, membership=mem_a, skill=skill_a, level=2, skill_version=1
        )
    with tenant_context(tenant_b.id):
        SkillAssertion.objects.create(
            tenant=tenant_b, membership=mem_b, skill=skill_b, level=2, skill_version=1
        )

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/skills/assertions/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()["results"]}
    assert str(a_assertion.id) in ids
    assert len(ids) == 1  # tenant B never leaks


@pytest.mark.django_db
def test_record_assertion_is_idempotent():
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, _, membership = _seed_tenant("acme", "a@acme.test", ["skill.verify"])
    skill = _tenant_skill(tenant)
    client = APIClient()
    token = _login(client, "a@acme.test")
    payload = {"membership": str(membership.id), "skill": str(skill.id), "level": 2}
    headers = {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_IDEMPOTENCY_KEY": "assert-1",
    }
    r1 = client.post("/api/skills/assertions/", payload, format="json", **headers)
    r2 = client.post("/api/skills/assertions/", payload, format="json", **headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    with tenant_context(tenant.id):
        assert SkillAssertion.objects.count() == 1
