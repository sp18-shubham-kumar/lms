import pytest
from rest_framework.test import APIClient


def _seed_tenant(slug, email, cap_keys, role_name="Admin"):
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name=role_name, is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person, membership


def _add_person(tenant, email):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    return person


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


@pytest.mark.django_db
def test_roles_list_returns_roles_with_capabilities():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite", "directory.view"])
    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.get(
        "/api/authz/roles/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    rows = resp.json()["results"]
    admin_row = next(r for r in rows if r["name"] == "Admin")
    assert "member.invite" in admin_row["capabilities"]


@pytest.mark.django_db
def test_roles_list_denied_without_capability():
    tenant, _, _ = _seed_tenant("acme", "x@acme.test", [])  # no member.invite
    client = APIClient()
    token = _login(client, "x@acme.test")
    resp = client.get(
        "/api/authz/roles/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_create_grant_audited():
    from apps.authz.models import Role, RoleGrant
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    target = _add_person(tenant, "newbie@acme.test")
    with tenant_context(tenant.id):
        learner = Role.objects.create(tenant=tenant, name="Learner", is_system=True)

    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.post(
        "/api/authz/grants/",
        {"principal_id": str(target.id), "role": str(learner.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    with tenant_context(tenant.id):
        assert RoleGrant.objects.filter(principal_id=target.id, role=learner).exists()
    assert AuditLog.objects.filter(action="member.grant").exists()


@pytest.mark.django_db
def test_create_grant_denied_without_capability():
    from apps.authz.models import Role
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "x@acme.test", ["directory.view"])  # no member.invite
    target = _add_person(tenant, "newbie@acme.test")
    with tenant_context(tenant.id):
        learner = Role.objects.create(tenant=tenant, name="Learner", is_system=True)

    client = APIClient()
    token = _login(client, "x@acme.test")
    resp = client.post(
        "/api/authz/grants/",
        {"principal_id": str(target.id), "role": str(learner.id)},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_delete_grant_requires_offboard_capability():
    from apps.authz.models import Role, RoleGrant
    from core.context import tenant_context

    # Admin holds member.invite but NOT member.offboard → DELETE must 403.
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    target = _add_person(tenant, "newbie@acme.test")
    with tenant_context(tenant.id):
        learner = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        grant = RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=target.id, role=learner
        )

    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.delete(
        f"/api/authz/grants/{grant.id}/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_delete_grant_with_offboard_audited():
    from apps.authz.models import Role, RoleGrant
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite", "member.offboard"])
    target = _add_person(tenant, "newbie@acme.test")
    with tenant_context(tenant.id):
        learner = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        grant = RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=target.id, role=learner
        )

    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.delete(
        f"/api/authz/grants/{grant.id}/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 204
    with tenant_context(tenant.id):
        assert not RoleGrant.objects.filter(id=grant.id).exists()
    assert AuditLog.objects.filter(action="member.offboard").exists()


@pytest.mark.django_db
def test_grants_list_is_tenant_isolated():
    from apps.authz.models import Role, RoleGrant
    from core.context import tenant_context

    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", ["member.invite"])
    target_b = _add_person(tenant_b, "bob@nw.test")
    with tenant_context(tenant_b.id):
        role_b = Role.objects.create(tenant=tenant_b, name="Learner", is_system=True)
        grant_b = RoleGrant.objects.create(
            tenant=tenant_b, principal_type="person", principal_id=target_b.id, role=role_b
        )

    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.get(
        "/api/authz/grants/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()["results"]}
    assert str(grant_b.id) not in ids  # tenant B's grants never leak
