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
    # Nothing written.
    assert Person.objects.count() == before_persons
    assert Membership.all_tenants.filter(tenant=tenant).count() == before_members


@pytest.mark.django_db
def test_commit_creates_persons_and_memberships():
    from django.contrib.auth import get_user_model

    from apps.authz.models import RoleGrant
    from apps.identity.models import Membership
    from core.context import tenant_context
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
    assert Person.objects.filter(email="new@acme.test").exists()
    new_person = Person.objects.get(email="new@acme.test")
    with tenant_context(tenant.id):
        assert Membership.objects.filter(person=new_person).exists()
        from apps.authz.models import Role

        learner = Role.objects.get(tenant=tenant, name="Learner")
        assert RoleGrant.objects.filter(principal_id=new_person.id, role=learner).exists()
    assert AuditLog.objects.filter(action="member.import").exists()


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
    # Exactly one person + one membership created despite two POSTs.
    assert Person.objects.filter(email="new@acme.test").count() == 1
    with tenant_context(tenant.id):
        assert Membership.objects.filter(person__email="new@acme.test").count() == 1


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
