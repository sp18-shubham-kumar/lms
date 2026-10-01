import re
from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone
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
        role = Role.objects.create(tenant=tenant, name="Admin", is_system=True)
        Role.objects.create(tenant=tenant, name="Learner", is_system=True)
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


def _auth(client, email, tenant):
    token = _login(client, email)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}


def _token_from_mail():
    match = re.search(r"token=(\S+)", mail.outbox[-1].body)
    assert match is not None
    return match.group(1)


@pytest.mark.django_db
def test_invite_emails_a_link_and_stores_only_the_hash():
    from apps.identity.invitation_service import hash_token
    from apps.identity.models import Invitation
    from core.models import AuditLog

    tenant, admin = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    client = APIClient()
    resp = client.post(
        "/api/identity/invitations/",
        {"email": "New@Acme.test", "role": "Learner"},
        format="json",
        **_auth(client, "admin@acme.test", tenant),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new@acme.test"
    assert body["role"] == "Learner"
    raw = body["token"]
    assert raw == _token_from_mail()
    assert (
        "token"
        not in client.get(
            "/api/identity/invitations/", **_auth(client, "admin@acme.test", tenant)
        ).json()["results"][0]
    )
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["new@acme.test"]
    invitation = Invitation.all_tenants.get(email="new@acme.test")
    assert invitation.token_hash == hash_token(raw)
    assert invitation.token_hash != raw
    assert AuditLog.objects.filter(action="member.invite", actor=admin).exists()


@pytest.mark.django_db
def test_invite_rejects_unknown_role_and_a_second_pending_invite():
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    client = APIClient()
    auth = _auth(client, "admin@acme.test", tenant)
    unknown = client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Nope"},
        format="json",
        **auth,
    )
    assert unknown.status_code == 400
    assert mail.outbox == []

    created = client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **auth,
    )
    assert created.status_code == 201
    again = client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **auth,
    )
    assert again.status_code == 400


@pytest.mark.django_db
def test_invite_rejects_a_role_that_belongs_to_another_tenant():
    from apps.authz.models import Role
    from core.context import tenant_context

    acme, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    north, _ = _seed_tenant("north", "admin@north.test", ["member.invite"])
    with tenant_context(acme.id):
        Role.objects.create(tenant=acme, name="Mentor", is_system=False)

    client = APIClient()
    resp = client.post(
        "/api/identity/invitations/",
        {"email": "new@north.test", "role": "Mentor"},
        format="json",
        **_auth(client, "admin@north.test", north),
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Unknown role: Mentor"


@pytest.mark.django_db
def test_invite_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "learner@acme.test", [])
    client = APIClient()
    resp = client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **_auth(client, "learner@acme.test", tenant),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_invitation_list_is_tenant_isolated():
    acme, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    north, _ = _seed_tenant("north", "admin@north.test", ["member.invite"])
    client = APIClient()
    created = client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **_auth(client, "admin@acme.test", acme),
    )
    assert created.status_code == 201

    listed = client.get("/api/identity/invitations/", **_auth(client, "admin@north.test", north))
    assert listed.status_code == 200
    emails = [row["email"] for row in listed.json()["results"]]
    assert "new@acme.test" not in emails

    own = client.get("/api/identity/invitations/", **_auth(client, "admin@acme.test", acme))
    assert [row["email"] for row in own.json()["results"]] == ["new@acme.test"]


@pytest.mark.django_db
def test_accept_creates_person_membership_and_lets_them_sign_in():
    from apps.authz.models import RoleGrant
    from apps.identity.models import Invitation, Membership
    from core.context import tenant_context

    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    client = APIClient()
    client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **_auth(client, "admin@acme.test", tenant),
    )
    raw = _token_from_mail()

    accepted = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw, "password": "Invite-pass-123"},
        format="json",
    )
    assert accepted.status_code == 200
    assert accepted.json()["email"] == "new@acme.test"

    login = client.post(
        "/api/auth/login/",
        {"email": "new@acme.test", "password": "Invite-pass-123"},
        format="json",
    )
    assert login.status_code == 200
    assert login.json()["memberships"][0]["tenant_id"] == str(tenant.id)

    with tenant_context(tenant.id):
        assert Membership.objects.filter(person__email="new@acme.test", status="active").exists()
        assert RoleGrant.objects.filter(role__name="Learner", principal_id__isnull=False).exists()
    assert Invitation.all_tenants.get(email="new@acme.test").status == "accepted"

    reused = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw, "password": "Invite-pass-123"},
        format="json",
    )
    assert reused.status_code == 400


@pytest.mark.django_db
def test_accept_rejects_an_expired_token():
    from apps.identity.models import Invitation

    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    client = APIClient()
    client.post(
        "/api/identity/invitations/",
        {"email": "new@acme.test", "role": "Learner"},
        format="json",
        **_auth(client, "admin@acme.test", tenant),
    )
    raw = _token_from_mail()
    Invitation.all_tenants.filter(email="new@acme.test").update(
        expires_at=timezone.now() - timedelta(days=1)
    )
    resp = client.post(
        "/api/auth/invitations/accept/",
        {"token": raw, "password": "Invite-pass-123"},
        format="json",
    )
    assert resp.status_code == 400
