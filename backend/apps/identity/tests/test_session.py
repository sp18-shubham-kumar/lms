import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_session_returns_person_tenant_capabilities():
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    tenant = Tenant.objects.create(
        slug="acme", name="Acme", status="active", plan="pro", accent_color="#4f46e5"
    )
    cap = Capability.objects.create(key="directory.view")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )

    client = APIClient()
    login = client.post(
        "/api/auth/login/", {"email": "a@acme.test", "password": "pw-12345"}, format="json"
    ).json()
    resp = client.get(
        "/api/auth/session/",
        HTTP_AUTHORIZATION=f"Bearer {login['access']}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["person"]["email"] == "a@acme.test"
    assert body["tenant"]["accent_color"] == "#4f46e5"
    assert "directory.view" in body["capabilities"]


@pytest.mark.django_db
def test_session_without_tenant_header_is_400():
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    client = APIClient()
    login = client.post(
        "/api/auth/login/", {"email": "a@acme.test", "password": "pw-12345"}, format="json"
    ).json()
    resp = client.get("/api/auth/session/", HTTP_AUTHORIZATION=f"Bearer {login['access']}")
    assert resp.status_code == 400
