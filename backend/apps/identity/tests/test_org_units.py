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


def _make_org_unit(tenant, name, path):
    from apps.identity.models import OrgUnit
    from core.context import tenant_context

    with tenant_context(tenant.id):
        return OrgUnit.objects.create(tenant=tenant, name=name, path=path)


@pytest.mark.django_db
def test_org_units_list_returns_tenant_units():
    tenant, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    _make_org_unit(tenant, "Engineering", "engineering")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/identity/org-units/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    names = {row["name"] for row in resp.json()["results"]}
    assert "Engineering" in names


@pytest.mark.django_db
def test_org_units_list_is_tenant_isolated():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    _make_org_unit(tenant_a, "A-Unit", "a")
    _make_org_unit(tenant_b, "B-Unit", "b")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/identity/org-units/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    names = {row["name"] for row in resp.json()["results"]}
    assert "A-Unit" in names
    assert "B-Unit" not in names  # tenant B never leaks


@pytest.mark.django_db
def test_org_units_list_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "a@acme.test", [])  # no directory.view
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/identity/org-units/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403
