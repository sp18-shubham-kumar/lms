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
        role = Role.objects.create(tenant=tenant, name="Admin", is_system=True)
        # The roles members may be imported into.
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


CSV_HEADER = "email,display_name,org_unit_path,role,employee_ref\n"


@pytest.mark.django_db
def test_dry_run_writes_nothing_and_reports_diff():
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership

    Person = get_user_model()
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])

    before_persons = Person.objects.count()
    before_members = Membership.all_tenants.filter(tenant=tenant).count()

    csv_body = CSV_HEADER + (
        "new@acme.test,New Person,,Learner,E100\n" "bad-row-without-email,,,Learner,E200\n"
    )
    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.post(
        "/api/identity/members/import/",
        data=csv_body,
        content_type="text/csv",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["adds"]) == 1
    assert body["adds"][0]["email"] == "new@acme.test"
    assert len(body["errors"]) == 1
    assert body["errors"][0]["row"] == 2
    assert "invited" not in body["adds"][0]
    # Nothing written.
    assert Person.objects.count() == before_persons
    assert Membership.all_tenants.filter(tenant=tenant).count() == before_members
    from apps.identity.models import Invitation

    assert not Invitation.all_tenants.filter(tenant=tenant).exists()


@pytest.mark.django_db
def test_commit_invites_new_emails_without_a_membership():
    from django.contrib.auth import get_user_model
    from django.core import mail

    from apps.identity.models import Invitation, Membership
    from core.models import AuditLog

    Person = get_user_model()
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])

    csv_body = CSV_HEADER + "new@acme.test,New Person,,Learner,E100\n"
    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.post(
        "/api/identity/members/import/?commit=true",
        data=csv_body,
        content_type="text/csv",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    assert resp.json()["adds"][0]["invited"] is True
    assert not Person.objects.filter(email="new@acme.test").exists()
    assert not Membership.all_tenants.filter(tenant=tenant, person__email="new@acme.test").exists()
    invitation = Invitation.all_tenants.select_related("role").get(
        tenant=tenant, email="new@acme.test"
    )
    assert invitation.status == "pending"
    assert invitation.role.name == "Learner"
    assert "/invite/accept?token=" in mail.outbox[0].body
    assert AuditLog.objects.filter(action="member.import").exists()


@pytest.mark.django_db
def test_commit_updates_org_unit_and_employee_ref_without_inviting():
    from django.contrib.auth import get_user_model

    from apps.authz.models import RoleGrant
    from apps.identity.models import Invitation, Membership, OrgUnit
    from core.context import tenant_context

    Person = get_user_model()
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    member = Person.objects.create_user(
        email="member@acme.test", display_name="Member", password="pw-12345"
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(
            person=member, tenant=tenant, status="suspended", employee_ref="OLD"
        )
        OrgUnit.objects.create(tenant=tenant, name="Engineering", path="engineering")
        grants_before = RoleGrant.objects.filter(principal_id=member.id).count()

    csv_body = CSV_HEADER + (
        "member@acme.test,Member,engineering,Learner,E900\n"
        "new@acme.test,New Person,,Learner,E100\n"
    )
    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.post(
        "/api/identity/members/import/?commit=true",
        data=csv_body,
        content_type="text/csv",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["adds"][0]["email"] == "new@acme.test"
    assert body["adds"][0]["invited"] is True
    assert body["updates"][0]["email"] == "member@acme.test"
    assert "invited" not in body["updates"][0]
    assert body["errors"] == []

    membership.refresh_from_db()
    assert membership.employee_ref == "E900"
    assert membership.org_unit is not None
    assert membership.org_unit.path == "engineering"
    assert membership.status == "suspended"
    assert member.check_password("pw-12345")
    assert not Invitation.all_tenants.filter(tenant=tenant, email="member@acme.test").exists()
    invitation = Invitation.all_tenants.select_related("role").get(
        tenant=tenant, email="new@acme.test"
    )
    assert invitation.status == "pending"
    assert invitation.role.name == "Learner"
    assert not Person.objects.filter(email="new@acme.test").exists()
    assert not Membership.all_tenants.filter(tenant=tenant, person__email="new@acme.test").exists()
    with tenant_context(tenant.id):
        assert RoleGrant.objects.filter(principal_id=member.id).count() == grants_before


@pytest.mark.django_db
def test_missing_role_is_an_error_and_not_invited():
    from apps.identity.models import Invitation

    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    csv_body = CSV_HEADER + "new@acme.test,New Person,,,E100\n"
    client = APIClient()
    token = _login(client, "admin@acme.test")
    headers = {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_TENANT_ID": str(tenant.id),
    }
    preview = client.post(
        "/api/identity/members/import/",
        data=csv_body,
        content_type="text/csv",
        **headers,
    )
    assert preview.status_code == 200
    assert preview.json()["adds"] == []
    assert preview.json()["errors"][0]["reason"] == "missing role"

    committed = client.post(
        "/api/identity/members/import/?commit=true",
        data=csv_body,
        content_type="text/csv",
        **headers,
    )
    assert committed.status_code == 200
    assert committed.json()["adds"] == []
    assert not Invitation.all_tenants.filter(tenant=tenant, email="new@acme.test").exists()


@pytest.mark.django_db
def test_malformed_role_row_is_error_not_committed():
    from django.contrib.auth import get_user_model

    Person = get_user_model()
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])

    csv_body = CSV_HEADER + "ghost@acme.test,Ghost,,NoSuchRole,E300\n"
    client = APIClient()
    token = _login(client, "admin@acme.test")
    resp = client.post(
        "/api/identity/members/import/?commit=true",
        data=csv_body,
        content_type="text/csv",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["errors"]) == 1
    assert not Person.objects.filter(email="ghost@acme.test").exists()


@pytest.mark.django_db
def test_commit_is_idempotent_with_idempotency_key():
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    tenant, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])

    csv_body = CSV_HEADER + "new@acme.test,New Person,,Learner,E100\n"
    client = APIClient()
    token = _login(client, "admin@acme.test")
    auth = {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_IDEMPOTENCY_KEY": "import-k1",
    }
    url = "/api/identity/members/import/?commit=true"
    r1 = client.post(url, data=csv_body, content_type="text/csv", **auth)
    r2 = client.post(url, data=csv_body, content_type="text/csv", **auth)
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Exactly one invitation despite two POSTs. No membership until they accept.
    from apps.identity.models import Invitation

    assert not Person.objects.filter(email="new@acme.test").exists()
    with tenant_context(tenant.id):
        assert Invitation.objects.filter(email="new@acme.test").count() == 1
        assert not Membership.objects.filter(person__email="new@acme.test").exists()


@pytest.mark.django_db
def test_import_denied_without_capability():
    tenant, _ = _seed_tenant("acme", "x@acme.test", [])  # no member.invite
    csv_body = CSV_HEADER + "new@acme.test,New Person,,Learner,E100\n"
    client = APIClient()
    token = _login(client, "x@acme.test")
    resp = client.post(
        "/api/identity/members/import/",
        data=csv_body,
        content_type="text/csv",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403
