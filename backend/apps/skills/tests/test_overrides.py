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


def _global_skill():
    from apps.skills.models import Skill, SkillDomain

    gd = SkillDomain.objects.create(tenant=None, name="Global")
    return Skill.objects.create(
        tenant=None, domain=gd, name="Global SQL", slug="global-sql", status="published"
    )


@pytest.mark.django_db
def test_put_levels_replaces_rubric_grid():
    from apps.skills.models import SkillLevel

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    gs = _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}

    resp = client.put(
        f"/api/skills/{gs.id}/levels/",
        {
            "levels": [
                {"level": 1, "title": "Beginner", "indicators": ["a"], "evidence_kinds": ["quiz"]},
                {"level": 2, "title": "Intermediate"},
            ]
        },
        format="json",
        **auth,
    )
    assert resp.status_code == 200
    assert SkillLevel.objects.filter(skill=gs).count() == 2

    # Replace with a single level: grid is replaced wholesale.
    resp2 = client.put(
        f"/api/skills/{gs.id}/levels/",
        {"levels": [{"level": 1, "title": "Only"}]},
        format="json",
        **auth,
    )
    assert resp2.status_code == 200
    assert SkillLevel.objects.filter(skill=gs).count() == 1

    # GET returns the grid.
    resp3 = client.get(f"/api/skills/{gs.id}/levels/", **auth)
    assert resp3.status_code == 200
    assert len(resp3.json()["levels"]) == 1


@pytest.mark.django_db
def test_override_rename_is_copy_on_write_per_tenant():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view", "taxonomy.edit"])
    gs = _global_skill()

    client = APIClient()
    token_a = _login(client, "a@acme.test")
    auth_a = {"HTTP_AUTHORIZATION": f"Bearer {token_a}", "HTTP_X_TENANT_ID": str(tenant_a.id)}

    resp = client.post(
        f"/api/skills/{gs.id}/override/",
        {"name": "Acme SQL"},
        format="json",
        **auth_a,
    )
    assert resp.status_code in (200, 201)

    # Tenant A sees the renamed skill.
    list_a = client.get("/api/skills/", **auth_a).json()["results"]
    a_row = next(r for r in list_a if r["id"] == str(gs.id))
    assert a_row["name"] == "Acme SQL"

    # Global row untouched.
    gs.refresh_from_db()
    assert gs.name == "Global SQL"

    # Tenant B still sees the global name.
    client_b = APIClient()
    token_b = _login(client_b, "b@nw.test")
    auth_b = {"HTTP_AUTHORIZATION": f"Bearer {token_b}", "HTTP_X_TENANT_ID": str(tenant_b.id)}
    list_b = client_b.get("/api/skills/", **auth_b).json()["results"]
    b_row = next(r for r in list_b if r["id"] == str(gs.id))
    assert b_row["name"] == "Global SQL"


@pytest.mark.django_db
def test_override_hidden_removes_skill_from_tenant_list():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    gs = _global_skill()

    client = APIClient()
    token_a = _login(client, "a@acme.test")
    auth_a = {"HTTP_AUTHORIZATION": f"Bearer {token_a}", "HTTP_X_TENANT_ID": str(tenant_a.id)}

    client.post(
        f"/api/skills/{gs.id}/override/",
        {"hidden": True},
        format="json",
        **auth_a,
    )
    list_a = client.get("/api/skills/", **auth_a).json()["results"]
    assert str(gs.id) not in {r["id"] for r in list_a}

    # Tenant B still sees it.
    client_b = APIClient()
    token_b = _login(client_b, "b@nw.test")
    auth_b = {"HTTP_AUTHORIZATION": f"Bearer {token_b}", "HTTP_X_TENANT_ID": str(tenant_b.id)}
    list_b = client_b.get("/api/skills/", **auth_b).json()["results"]
    assert str(gs.id) in {r["id"] for r in list_b}


@pytest.mark.django_db
def test_edges_endpoint_rejects_cycle_with_400():
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    with tenant_context(tenant.id):
        gd = SkillDomain.objects.create(tenant=tenant, name="D")
        a = Skill.objects.create(tenant=tenant, domain=gd, name="A", slug="a")
        b = Skill.objects.create(tenant=tenant, domain=gd, name="B", slug="b")

    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}

    r1 = client.post(
        f"/api/skills/{a.id}/edges/",
        {"to_skill": str(b.id), "kind": "prerequisite"},
        format="json",
        **auth,
    )
    assert r1.status_code in (200, 201)

    r2 = client.post(
        f"/api/skills/{b.id}/edges/",
        {"to_skill": str(a.id), "kind": "prerequisite"},
        format="json",
        **auth,
    )
    assert r2.status_code == 400

    # list + delete
    r3 = client.get(f"/api/skills/{a.id}/edges/", **auth)
    assert r3.status_code == 200
    assert len(r3.json()["edges"]) == 1
    edge_id = r3.json()["edges"][0]["id"]
    r4 = client.delete(f"/api/skills/{a.id}/edges/?edge={edge_id}", **auth)
    assert r4.status_code in (200, 204)


@pytest.mark.django_db
def test_override_denied_without_taxonomy_edit():
    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])  # no taxonomy.edit
    gs = _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        f"/api/skills/{gs.id}/override/",
        {"name": "Nope"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_tenant_skill_override_uniqueness():
    from django.db import IntegrityError

    from apps.skills.models import TenantSkillOverride
    from core.context import tenant_context

    tenant, _ = _seed_tenant("acme", "a@acme.test", [])
    gs = _global_skill()
    with tenant_context(tenant.id):
        TenantSkillOverride.objects.create(tenant=tenant, skill=gs, name="X")
        with pytest.raises(IntegrityError):
            TenantSkillOverride.objects.create(tenant=tenant, skill=gs, name="Y")
