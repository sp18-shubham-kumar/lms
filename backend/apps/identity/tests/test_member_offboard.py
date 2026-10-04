import pytest
from rest_framework.test import APIClient

from apps.identity.tests.test_person_profile import _add_member, _login, _seed_tenant


def _offboard(client, email, tenant, person_id):
    token = _login(client, email)
    return client.post(
        f"/api/identity/people/{person_id}/offboard/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )


@pytest.mark.django_db
def test_offboard_ends_membership_revokes_grants_and_audits():
    from apps.authz.models import Role, RoleGrant
    from apps.identity.models import Membership
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.offboard", "directory.view"])
    person, membership = _add_member(tenant, "leaver@acme.test")
    with tenant_context(tenant.id):
        role = Role.objects.create(tenant=tenant, name="Learner")
        RoleGrant.objects.create(tenant=tenant, principal_id=person.id, role=role)

    resp = _offboard(APIClient(), "admin@acme.test", tenant, person.id)

    assert resp.status_code == 204
    with tenant_context(tenant.id):
        membership = Membership.objects.get(id=membership.id)
        assert membership.status == "ended"
        assert membership.ended_at is not None
        assert not RoleGrant.objects.filter(principal_id=person.id).exists()
    log = AuditLog.objects.get(action="member.offboard")
    assert log.metadata["grants_revoked"] == 1

    client = APIClient()
    token = _login(client, "admin@acme.test")
    listing = client.get(
        "/api/identity/people/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert "leaver@acme.test" not in {r["email"] for r in listing.json()["results"]}


@pytest.mark.django_db
def test_offboard_denied_without_capability():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.invite"])
    person, _ = _add_member(tenant, "leaver@acme.test")

    resp = _offboard(APIClient(), "admin@acme.test", tenant, person.id)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_cannot_offboard_yourself():
    tenant, admin, _ = _seed_tenant("acme", "admin@acme.test", ["member.offboard"])

    resp = _offboard(APIClient(), "admin@acme.test", tenant, admin.id)

    assert resp.status_code == 400


@pytest.mark.django_db
def test_cannot_offboard_a_member_of_another_tenant():
    from apps.identity.models import Membership

    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["member.offboard"])
    tenant_b, outsider, membership_b = _seed_tenant("northwind", "b@nw.test", [])

    resp = _offboard(APIClient(), "admin@acme.test", tenant_a, outsider.id)

    assert resp.status_code == 404
    assert Membership.all_tenants.get(id=membership_b.id).status == "active"
