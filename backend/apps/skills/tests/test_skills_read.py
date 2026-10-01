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
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


def _seed_skills(tenant_a, tenant_b):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    gd = SkillDomain.objects.create(tenant=None, name="Global")
    gs = Skill.objects.create(
        tenant=None, domain=gd, name="Global SQL", slug="global-sql", status="published"
    )
    with tenant_context(tenant_a.id):
        sa = Skill.objects.create(
            tenant=tenant_a, domain=gd, name="A dbt", slug="a-dbt", status="published"
        )
    with tenant_context(tenant_b.id):
        sb = Skill.objects.create(
            tenant=tenant_b, domain=gd, name="B kafka", slug="b-kafka", status="published"
        )
    return gs, sa, sb


@pytest.mark.django_db
def test_skills_list_is_tenant_isolated_with_globals():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    gs, sa, sb = _seed_skills(tenant_a, tenant_b)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/skills/skills/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()["results"]}
    assert str(gs.id) in ids  # global visible
    assert str(sa.id) in ids  # own tenant visible
    assert str(sb.id) not in ids  # tenant B never leaks


@pytest.mark.django_db
def test_skills_list_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "a@acme.test", [])  # no directory.view
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/skills/skills/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_skill_retrieve_and_domains_list():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    gs, sa, sb = _seed_skills(tenant_a, tenant_b)

    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant_a.id)}

    # retrieve own skill
    resp = client.get(f"/api/skills/skills/{sa.id}/", **auth)
    assert resp.status_code == 200
    assert resp.json()["name"] == "A dbt"

    # cannot retrieve tenant B's skill
    resp_b = client.get(f"/api/skills/skills/{sb.id}/", **auth)
    assert resp_b.status_code == 404

    # domains list includes the global domain
    resp_d = client.get("/api/skills/domains/", **auth)
    assert resp_d.status_code == 200
    names = {row["name"] for row in resp_d.json()["results"]}
    assert "Global" in names


@pytest.mark.django_db
def test_domains_list_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "a@acme.test", [])
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/skills/domains/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403
