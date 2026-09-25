import pytest
from rest_framework.test import APIClient


def _person_with_membership(email="a@acme.test", pw="pw-12345", status="active"):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email=email, display_name="A", password=pw)
    tenant = Tenant.objects.create(
        slug="acme", name="Acme", status="active", plan="pro", accent_color="#4f46e5"
    )
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status=status)
    return person, tenant


@pytest.mark.django_db
def test_login_returns_tokens_and_memberships():
    _person_with_membership()
    resp = APIClient().post(
        "/api/auth/login/", {"email": "a@acme.test", "password": "pw-12345"}, format="json"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["access"] and body["refresh"]
    assert body["memberships"][0]["slug"] == "acme"
    assert body["memberships"][0]["accent_color"] == "#4f46e5"


@pytest.mark.django_db
def test_login_bad_password_is_401():
    _person_with_membership()
    resp = APIClient().post(
        "/api/auth/login/", {"email": "a@acme.test", "password": "wrong"}, format="json"
    )
    assert resp.status_code == 401


@pytest.mark.django_db
def test_login_without_active_membership_is_403():
    _person_with_membership(status="ended")
    resp = APIClient().post(
        "/api/auth/login/", {"email": "a@acme.test", "password": "pw-12345"}, format="json"
    )
    assert resp.status_code == 403
