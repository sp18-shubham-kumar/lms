"""
Middleware-level tenant membership enforcement.

A request whose authenticated user has no active Membership in the tenant named
by ``X-Tenant-Id`` must be rejected (403 JSON) before any view runs. Public /
unauthenticated endpoints must keep working (no tenant/user requirement).
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from core.context import tenant_context

Person = get_user_model()


def _login(client: APIClient, email: str, password: str) -> str:
    resp = client.post(
        "/api/auth/login/", {"email": email, "password": password}, format="json"
    ).json()
    return str(resp["access"])


@pytest.mark.django_db
def test_active_member_passes() -> None:
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")

    client = APIClient()
    token = _login(client, "a@acme.test", "pw-12345")
    resp = client.get(
        "/api/auth/session/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200


@pytest.mark.django_db
def test_non_member_tenant_header_is_403() -> None:
    from apps.identity.models import Membership, Tenant

    tenant_a = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    tenant_b = Tenant.objects.create(slug="beta", name="Beta", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    with tenant_context(tenant_a.id):
        Membership.objects.create(person=person, tenant=tenant_a, status="active")

    client = APIClient()
    token = _login(client, "a@acme.test", "pw-12345")
    resp = client.get(
        "/api/auth/session/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_b.id),
    )
    assert resp.status_code == 403
    assert "detail" in resp.json()


@pytest.mark.django_db
def test_ended_membership_is_403() -> None:
    from apps.identity.models import Membership, Tenant

    # Active membership in home tenant so login succeeds; ended membership in the
    # target tenant whose header is sent -> middleware must reject.
    home = Tenant.objects.create(slug="home", name="Home", status="active", plan="pro")
    target = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    with tenant_context(home.id):
        Membership.objects.create(person=person, tenant=home, status="active")
    with tenant_context(target.id):
        Membership.objects.create(person=person, tenant=target, status="ended")

    client = APIClient()
    token = _login(client, "a@acme.test", "pw-12345")
    resp = client.get(
        "/api/auth/session/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(target.id),
    )
    assert resp.status_code == 403
    assert "detail" in resp.json()


@pytest.mark.django_db
def test_public_endpoint_without_tenant_or_auth_still_works() -> None:
    """Health check: no tenant header, no auth -> middleware must not reject."""
    client = APIClient()
    resp = client.get("/api/health/")
    assert resp.status_code == 200


@pytest.mark.django_db
def test_login_endpoint_unaffected_by_middleware() -> None:
    """Login is public: a stray tenant header on an unauthenticated request is fine.

    The request is unauthenticated (no Bearer token) so the middleware must not
    apply the membership check even though a tenant header is present.
    """
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A", password="pw-12345")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")

    client = APIClient()
    resp = client.post(
        "/api/auth/login/",
        {"email": "a@acme.test", "password": "pw-12345"},
        format="json",
        HTTP_X_TENANT_ID="00000000-0000-0000-0000-000000000000",
    )
    assert resp.status_code == 200
