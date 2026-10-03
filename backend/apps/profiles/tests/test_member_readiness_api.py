"""
Manager drill-down + heatmap readiness (P2-R7, P2-R8).

- GET /api/profiles/members/{membership}/readiness/?target=  (report.org.view)
- The heatmap computes readiness for members who have no snapshot yet.
"""

import pytest
from rest_framework.test import APIClient

from apps.profiles.tests.test_readiness_api import _login, _seed_profile, _seed_tenant


def _add_member(tenant, email, assertions=()):
    """An active learner in ``tenant`` with verified (skill, level) assertions."""
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    person = get_user_model().objects.create_user(
        email=email, display_name="Bob Learner", password="pw-12345"
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        for skill, level in assertions:
            SkillAssertion.objects.create(
                tenant=tenant, membership=membership, skill=skill, level=level, skill_version=1
            )
    return membership


def _manager_client(tenant, email):
    client = APIClient()
    token = _login(client, email)
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant.id))
    return client


@pytest.mark.django_db
def test_manager_sees_a_members_gap():
    tenant, _, _ = _seed_tenant("acme", "m@acme.test", ["report.org.view"])
    profile, sql, python, _dbt = _seed_profile(tenant)
    bob = _add_member(tenant, "bob@acme.test", [(sql, 3), (python, 1)])

    resp = _manager_client(tenant, "m@acme.test").get(
        f"/api/profiles/members/{bob.id}/readiness/?target={profile.id}"
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Bob Learner"
    assert body["membership_id"] == str(bob.id)
    assert (body["met"], body["total"], body["readiness_pct"]) == (1, 2, 50)
    by_skill = {r["skill_name"]: r for r in body["requirements"]}
    assert by_skill["SQL"]["status"] == "met"
    assert by_skill["Python"]["status"] == "close"
    assert by_skill["Python"]["current_level"] == 1
    assert by_skill["dbt"]["status"] == "not_started"
    # Unmet first, met last.
    assert body["requirements"][-1]["skill_name"] == "SQL"


@pytest.mark.django_db
def test_member_readiness_uses_highest_verified_level():
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "m@acme.test", ["report.org.view"])
    profile, sql, python, _dbt = _seed_profile(tenant)
    bob = _add_member(tenant, "bob@acme.test", [(python, 4)])
    with tenant_context(tenant.id):
        SkillAssertion.objects.create(
            tenant=tenant, membership=bob, skill=python, level=1, skill_version=1
        )

    body = (
        _manager_client(tenant, "m@acme.test")
        .get(f"/api/profiles/members/{bob.id}/readiness/?target={profile.id}")
        .json()
    )
    python_row = next(r for r in body["requirements"] if r["skill_name"] == "Python")
    assert python_row["current_level"] == 4
    assert python_row["status"] == "met"


@pytest.mark.django_db
def test_member_readiness_denied_without_report_org_view():
    tenant, _, _ = _seed_tenant("acme", "l@acme.test", ["skill.claim.submit", "directory.view"])
    profile, *_ = _seed_profile(tenant)
    bob = _add_member(tenant, "bob@acme.test")

    resp = _manager_client(tenant, "l@acme.test").get(
        f"/api/profiles/members/{bob.id}/readiness/?target={profile.id}"
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_member_readiness_cannot_reach_another_tenants_member():
    acme, _, _ = _seed_tenant("acme", "m@acme.test", ["report.org.view"])
    acme_profile, *_ = _seed_profile(acme)
    globex, _, _ = _seed_tenant("globex", "g@globex.test", [])
    outsider = _add_member(globex, "spy@globex.test")

    resp = _manager_client(acme, "m@acme.test").get(
        f"/api/profiles/members/{outsider.id}/readiness/?target={acme_profile.id}"
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_member_readiness_requires_target():
    tenant, _, _ = _seed_tenant("acme", "m@acme.test", ["report.org.view"])
    bob = _add_member(tenant, "bob@acme.test")
    resp = _manager_client(tenant, "m@acme.test").get(f"/api/profiles/members/{bob.id}/readiness/")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_heatmap_computes_readiness_for_members_without_a_snapshot():
    """A member who never opened the target still shows their verified skills as met."""
    from apps.identity.models import OrgUnit
    from apps.profiles.models import ReadinessSnapshot
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "m@acme.test", ["report.org.view"])
    profile, sql, python, _dbt = _seed_profile(tenant)
    bob = _add_member(tenant, "bob@acme.test", [(sql, 2), (python, 3)])
    with tenant_context(tenant.id):
        unit = OrgUnit.objects.create(tenant=tenant, name="Data", path="/data")
        bob.org_unit = unit
        bob.save()
        assert not ReadinessSnapshot.objects.filter(membership=bob).exists()

    resp = _manager_client(tenant, "m@acme.test").get(
        f"/api/profiles/heatmap/?org_unit={unit.id}&job_profile={profile.id}"
    )
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) == 1
    assert [cell["met"] for cell in rows[0]["cells"]] == [True, True]
