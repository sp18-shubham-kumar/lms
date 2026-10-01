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


@pytest.mark.django_db
def test_people_list_is_tenant_isolated():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, person_b = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/identity/people/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert "a@acme.test" in emails
    assert "b@nw.test" not in emails  # tenant B never leaks


@pytest.mark.django_db
def test_people_list_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "a@acme.test", [])  # no directory.view
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/identity/people/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_people_list_cross_tenant_header_is_403():
    tenant_a, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    tenant_b, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "a@acme.test")  # member of A only
    resp = client.get(
        "/api/identity/people/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_b.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_people_list_excludes_ended_members():
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()

    tenant_a, active_person = _seed_tenant("acme", "active@acme.test", ["directory.view"])

    # Create a second person in tenant A with an ended membership
    ended_person = Person.objects.create_user(
        email="ended@acme.test", display_name="Ended Person", password="pw-12345"
    )
    with tenant_context(tenant_a.id):
        Membership.objects.create(person=ended_person, tenant=tenant_a, status="ended")

    client = APIClient()
    token = _login(client, "active@acme.test")
    resp = client.get(
        "/api/identity/people/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert "active@acme.test" in emails
    assert "ended@acme.test" not in emails  # ended membership must not appear
