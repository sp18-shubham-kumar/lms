import pytest
from rest_framework.test import APIClient

from apps.authz.tests.test_admin_endpoints import _add_person, _login, _seed_tenant


def _call(method, url, tenant, email="admin@acme.test", data=None):
    client = APIClient()
    token = _login(client, email)
    return getattr(client, method)(
        url,
        data,
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )


def _role(tenant, name="Learner"):
    from apps.authz.models import Role
    from core.context import tenant_context

    with tenant_context(tenant.id):
        return Role.objects.create(tenant=tenant, name=name)


@pytest.mark.django_db
def test_capability_list_returns_seeded_keys():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite", "skill.verify"])

    resp = _call("get", "/api/authz/capabilities/", tenant)

    assert resp.status_code == 200
    assert [row["key"] for row in resp.json()] == ["member.invite", "skill.verify"]


@pytest.mark.django_db
def test_capability_list_denied_without_member_invite():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["directory.view"])

    assert _call("get", "/api/authz/capabilities/", tenant).status_code == 403


@pytest.mark.django_db
def test_grant_list_filters_by_principal_and_names_the_role():
    tenant, admin, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    target = _add_person(tenant, "bob@acme.test")
    learner = _role(tenant)
    _call(
        "post",
        "/api/authz/grants/",
        tenant,
        data={"principal_id": str(target.id), "role": str(learner.id)},
    )

    resp = _call("get", f"/api/authz/grants/?principal_id={target.id}", tenant)

    rows = resp.json()["results"]
    assert [(r["principal_id"], r["role_name"]) for r in rows] == [(str(target.id), "Learner")]


@pytest.mark.django_db
def test_grant_to_non_member_is_rejected():
    import uuid

    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    learner = _role(tenant)

    resp = _call(
        "post",
        "/api/authz/grants/",
        tenant,
        data={"principal_id": str(uuid.uuid4()), "role": str(learner.id)},
    )

    assert resp.status_code == 400
    assert "principal_id" in resp.json()["error"]["detail"]


@pytest.mark.django_db
def test_grant_to_member_of_another_tenant_is_rejected():
    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    _, outsider, _ = _seed_tenant("northwind", "b@nw.test", [])
    learner = _role(tenant_a)

    resp = _call(
        "post",
        "/api/authz/grants/",
        tenant_a,
        data={"principal_id": str(outsider.id), "role": str(learner.id)},
    )

    assert resp.status_code == 400


@pytest.mark.django_db
def test_duplicate_grant_is_rejected():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    target = _add_person(tenant, "bob@acme.test")
    learner = _role(tenant)
    body = {"principal_id": str(target.id), "role": str(learner.id)}

    assert _call("post", "/api/authz/grants/", tenant, data=body).status_code == 201
    assert _call("post", "/api/authz/grants/", tenant, data=body).status_code == 400


@pytest.mark.django_db
def test_org_unit_scope_must_be_an_org_unit_of_this_tenant():
    from apps.identity.models import OrgUnit
    from core.context import tenant_context

    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", [])
    target = _add_person(tenant_a, "bob@acme.test")
    learner = _role(tenant_a)
    with tenant_context(tenant_a.id):
        own_unit = OrgUnit.objects.create(tenant=tenant_a, name="Data", path="data")
    with tenant_context(tenant_b.id):
        foreign_unit = OrgUnit.objects.create(tenant=tenant_b, name="Data", path="data")

    def grant(unit):
        return _call(
            "post",
            "/api/authz/grants/",
            tenant_a,
            data={
                "principal_id": str(target.id),
                "role": str(learner.id),
                "scope_type": "org_unit",
                "scope_id": str(unit.id),
            },
        )

    assert grant(foreign_unit).status_code == 400
    assert grant(own_unit).status_code == 201


@pytest.mark.django_db
def test_grant_with_role_from_another_tenant_is_rejected():
    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", [])
    target = _add_person(tenant_a, "bob@acme.test")
    foreign_role = _role(tenant_b, "Foreign")

    resp = _call(
        "post",
        "/api/authz/grants/",
        tenant_a,
        data={"principal_id": str(target.id), "role": str(foreign_role.id)},
    )

    assert resp.status_code == 400
