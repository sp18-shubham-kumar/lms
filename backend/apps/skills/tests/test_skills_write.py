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


def _global_domain():
    from apps.skills.models import SkillDomain

    return SkillDomain.objects.create(tenant=None, name="Global")


@pytest.mark.django_db
def test_create_skill_as_taxonomy_editor():
    from core.models import AuditLog

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    gd = _global_domain()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/",
        {"domain": str(gd.id), "name": "dbt", "slug": "dbt"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert AuditLog.objects.filter(action="skill.create").exists()


@pytest.mark.django_db
def test_create_skill_denied_without_taxonomy_edit():
    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])  # no taxonomy.edit
    gd = _global_domain()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/",
        {"domain": str(gd.id), "name": "dbt", "slug": "dbt"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_delete_retires_skill_without_deleting_row():
    from apps.skills.models import Skill
    from core.context import tenant_context

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    gd = _global_domain()
    with tenant_context(tenant.id):
        skill = Skill.objects.create(tenant=tenant, domain=gd, name="dbt", slug="dbt")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.delete(
        f"/api/skills/{skill.id}/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code in (200, 204)
    with tenant_context(tenant.id):
        skill.refresh_from_db()
    assert skill.status == "retired"


@pytest.mark.django_db
def test_cannot_write_global_skill():
    from apps.skills.models import Skill

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    gd = _global_domain()
    gs = Skill.objects.create(tenant=None, domain=gd, name="Global SQL", slug="global-sql")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.patch(
        f"/api/skills/{gs.id}/",
        {"name": "hacked"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code in (400, 403)
    gs.refresh_from_db()
    assert gs.name == "Global SQL"


@pytest.mark.django_db
def test_idempotent_create():
    from apps.skills.models import Skill
    from core.context import tenant_context

    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    gd = _global_domain()
    client = APIClient()
    token = _login(client, "a@acme.test")
    payload = {"domain": str(gd.id), "name": "dbt", "slug": "dbt"}
    headers = {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_IDEMPOTENCY_KEY": "key-1",
    }
    r1 = client.post("/api/skills/", payload, format="json", **headers)
    r2 = client.post("/api/skills/", payload, format="json", **headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    with tenant_context(tenant.id):
        assert Skill.objects.filter(slug="dbt").count() == 1
