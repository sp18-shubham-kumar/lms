import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient


def _operator(email="ops@platform.test"):
    from django.contrib.auth import get_user_model

    return get_user_model().objects.create_superuser(
        email=email, display_name="Ops", password="ops-pass-123"
    )


def _auth(client, email="ops@platform.test", password="ops-pass-123"):
    token = client.post(
        "/api/auth/login/", {"email": email, "password": password}, format="json"
    ).json()["access"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


BODY = {"name": "Sked", "slug": "sked", "admin_email": "admin@sked.test"}


def _token_from_mail() -> str:
    match = re.search(r"token=(\S+)", str(mail.outbox[-1].body))
    assert match is not None
    return match.group(1)


@pytest.mark.django_db
def test_operator_provisions_tenant_and_admin_joins_by_accepting():
    from django.contrib.auth import get_user_model

    from apps.authz.models import RoleCapability
    from apps.identity.invitation_service import hash_token
    from apps.identity.models import Invitation, Membership, Tenant
    from core.context import tenant_context

    _operator()
    client = APIClient()
    resp = client.post("/api/platform/tenants/", BODY, format="json", **_auth(client))
    assert resp.status_code == 201
    body = resp.json()
    assert body["tenant"]["slug"] == "sked"
    assert body["admin"]["email"] == "admin@sked.test"
    assert body["role"] == "Tenant Admin"
    assert body["invitation"]["status"] == "pending"
    assert body["invitation"]["email"] == "admin@sked.test"
    raw_token = body["invitation"]["token"]
    assert raw_token == _token_from_mail()

    person = get_user_model().objects.get(email="admin@sked.test")
    assert person.has_usable_password() is False
    assert Membership.all_tenants.filter(person=person).exists() is False

    tenant = Tenant.objects.get(slug="sked")
    with tenant_context(tenant.id):
        caps = set(
            RoleCapability.objects.filter(role__name="Tenant Admin").values_list(
                "capability__key", flat=True
            )
        )
    assert "member.invite" in caps

    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["admin@sked.test"]
    assert "/invite/accept?token=" in mail.outbox[0].body
    invitation = Invitation.all_tenants.get(tenant=tenant, email="admin@sked.test")
    assert invitation.token_hash == hash_token(raw_token)
    assert invitation.status == "pending"

    blocked = client.post(
        "/api/auth/login/",
        {"email": "admin@sked.test", "password": "Sked-admin-123"},
        format="json",
    )
    assert blocked.status_code == 401

    accepted = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw_token, "password": "Sked-admin-123"},
        format="json",
    )
    assert accepted.status_code == 200
    assert accepted.json()["email"] == "admin@sked.test"
    assert accepted.json()["tenant_id"] == str(tenant.id)

    person.refresh_from_db()
    assert person.has_usable_password() is True
    assert Membership.all_tenants.filter(person=person, tenant=tenant, status="active").exists()

    login = client.post(
        "/api/auth/login/",
        {"email": "admin@sked.test", "password": "Sked-admin-123"},
        format="json",
    )
    assert login.status_code == 200
    assert login.json()["memberships"][0]["slug"] == "sked"

    session = client.get(
        "/api/auth/session/",
        HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert session.status_code == 200
    assert "member.invite" in session.json()["capabilities"]

    again = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw_token, "password": "Sked-admin-123"},
        format="json",
    )
    assert again.status_code == 400


@pytest.mark.django_db
def test_accept_rejects_an_expired_token():
    _operator()
    client = APIClient()
    created = client.post("/api/platform/tenants/", BODY, format="json", **_auth(client))
    assert created.status_code == 201
    raw_token = _token_from_mail()

    from apps.identity.models import Invitation

    invitation = Invitation.all_tenants.get(email="admin@sked.test")
    invitation.expires_at = timezone.now() - timedelta(days=1)
    invitation.save(update_fields=["expires_at"])

    resp = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw_token, "password": "Sked-admin-123"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_provision_rejects_a_duplicate_slug_and_non_operators():
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    _operator()
    Tenant.objects.create(slug="sked", name="Existing", status="active", plan="pro")
    client = APIClient()
    auth = _auth(client)
    duplicate = client.post("/api/platform/tenants/", BODY, format="json", **auth)
    assert duplicate.status_code == 400

    Person = get_user_model()
    staff = Person.objects.create_user(
        email="staff@platform.test", display_name="Staff", password="pw-12345"
    )
    staff.is_staff = True
    staff.save(update_fields=["is_staff"])
    super_only = Person.objects.create_user(
        email="root@platform.test", display_name="Root", password="pw-12345"
    )
    super_only.is_superuser = True
    super_only.save(update_fields=["is_superuser"])
    holder = Tenant.objects.create(slug="holder", name="Holder", status="active", plan="pro")
    with tenant_context(holder.id):
        Membership.objects.create(person=staff, tenant=holder, status="active")
        Membership.objects.create(person=super_only, tenant=holder, status="active")

    staff_token = client.post(
        "/api/auth/login/",
        {"email": "staff@platform.test", "password": "pw-12345"},
        format="json",
    ).json()["access"]
    staff_resp = client.post(
        "/api/platform/tenants/",
        {"name": "Other", "slug": "other", "admin_email": "a@other.test"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {staff_token}",
    )
    assert staff_resp.status_code == 403

    super_token = client.post(
        "/api/auth/login/",
        {"email": "root@platform.test", "password": "pw-12345"},
        format="json",
    ).json()["access"]
    super_resp = client.post(
        "/api/platform/tenants/",
        {"name": "Other", "slug": "other", "admin_email": "a@other.test"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {super_token}",
    )
    assert super_resp.status_code == 403

    anon = client.post("/api/platform/tenants/", BODY, format="json")
    assert anon.status_code == 401
