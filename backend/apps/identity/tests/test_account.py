"""Tenant-independent account endpoints: the operator flag, /auth/me/, the tenant list."""

import pytest
from rest_framework.test import APIClient

PASSWORD = "pw-12345"


def _operator(email="ops@platform.test"):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_superuser(
        email=email, display_name="Ops", password=PASSWORD
    )


def _member(email="a@acme.test", slug="acme"):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    person = get_user_model().objects.create_user(email=email, display_name="A", password=PASSWORD)
    tenant = Tenant.objects.create(slug=slug, name=slug.title())
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    return person, tenant


def _login(client, email):
    return client.post("/api/auth/login/", {"email": email, "password": PASSWORD}, format="json")


def _bearer(client, email):
    return {"HTTP_AUTHORIZATION": f"Bearer {_login(client, email).json()['access']}"}


@pytest.mark.django_db
def test_login_flags_platform_operator_without_memberships():
    _operator()
    body = _login(APIClient(), "ops@platform.test").json()
    assert body["memberships"] == []
    assert body["is_platform_operator"] is True
    assert body["person"]["display_name"] == "Ops"


@pytest.mark.django_db
def test_login_does_not_flag_ordinary_member():
    _member()
    body = _login(APIClient(), "a@acme.test").json()
    assert body["is_platform_operator"] is False
    assert [m["slug"] for m in body["memberships"]] == ["acme"]


@pytest.mark.django_db
def test_staff_without_superuser_is_not_an_operator_and_cannot_log_in_tenantless():
    from django.contrib.auth import get_user_model

    get_user_model().objects.create_user(
        email="staff@platform.test", display_name="S", password=PASSWORD, is_staff=True
    )
    assert _login(APIClient(), "staff@platform.test").status_code == 403


@pytest.mark.django_db
def test_me_needs_no_tenant_header():
    _operator()
    client = APIClient()
    resp = client.get("/api/auth/me/", **_bearer(client, "ops@platform.test"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["person"]["email"] == "ops@platform.test"
    assert body["is_platform_operator"] is True
    assert body["memberships"] == []


@pytest.mark.django_db
def test_me_lists_member_memberships():
    _member()
    client = APIClient()
    body = client.get("/api/auth/me/", **_bearer(client, "a@acme.test")).json()
    assert body["is_platform_operator"] is False
    assert [m["slug"] for m in body["memberships"]] == ["acme"]


@pytest.mark.django_db
def test_me_requires_authentication():
    assert APIClient().get("/api/auth/me/").status_code == 401


@pytest.mark.django_db
def test_operator_lists_tenants_with_active_member_counts():
    from apps.identity.models import Membership
    from core.context import tenant_context

    _operator()
    _, acme = _member()
    other, _ = _member(email="b@acme.test", slug="globex")
    with tenant_context(acme.id):
        Membership.objects.create(person=other, tenant=acme, status="ended")

    client = APIClient()
    resp = client.get("/api/platform/tenants/", **_bearer(client, "ops@platform.test"))
    assert resp.status_code == 200
    counts = {t["slug"]: t["member_count"] for t in resp.json()}
    assert counts == {"acme": 1, "globex": 1}


@pytest.mark.django_db
def test_tenant_member_cannot_list_tenants():
    _member()
    client = APIClient()
    resp = client.get("/api/platform/tenants/", **_bearer(client, "a@acme.test"))
    assert resp.status_code == 403


@pytest.mark.django_db
def test_provisioned_invitation_carries_its_accept_link():
    _operator()
    client = APIClient()
    resp = client.post(
        "/api/platform/tenants/",
        {"name": "Sked", "slug": "sked", "admin_email": "admin@sked.test"},
        format="json",
        **_bearer(client, "ops@platform.test"),
    )
    invitation = resp.json()["invitation"]
    assert invitation["invite_url"].endswith(f"/invite/accept?token={invitation['token']}")


@pytest.mark.django_db
def test_session_reports_operator_flag_inside_a_tenant():
    person, tenant = _member()
    person.is_staff = person.is_superuser = True
    person.save()
    client = APIClient()
    resp = client.get(
        "/api/auth/session/", HTTP_X_TENANT_ID=str(tenant.id), **_bearer(client, "a@acme.test")
    )
    assert resp.status_code == 200
    assert resp.json()["is_platform_operator"] is True
