"""
Tests for Task 18: Readiness/gap + team + heatmap endpoints.

- GET /api/profiles/me/readiness/?target=<profile_id>  (skill.claim.submit)
- GET /api/profiles/readiness/?job_profile=<id>        (report.org.view)
- GET /api/profiles/heatmap/?org_unit=<id>&job_profile=<id>  (report.org.view)
"""

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
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person, membership


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


def _seed_profile(tenant):
    """Create a profile with 2 core + 1 supporting requirements. Returns (profile, sql_skill, python_skill, dbt_skill)."""
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name="Engineering")
        sql = Skill.objects.create(
            tenant=tenant, domain=domain, name="SQL", slug="sql", version=1, status="published"
        )
        python = Skill.objects.create(
            tenant=tenant,
            domain=domain,
            name="Python",
            slug="python",
            version=1,
            status="published",
        )
        dbt = Skill.objects.create(
            tenant=tenant, domain=domain, name="dbt", slug="dbt", version=1, status="published"
        )
        track = Track.objects.create(tenant=tenant, name="Data")
        profile = JobProfile.objects.create(
            tenant=tenant, track=track, grade=2, title="Data Engineer L2", status="published"
        )
        ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=sql, min_level=2, criticality="core"
        )
        ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=python, min_level=3, criticality="core"
        )
        ProfileRequirement.objects.create(
            tenant=tenant, job_profile=profile, skill=dbt, min_level=1, criticality="supporting"
        )
    return profile, sql, python, dbt


# ─── me/readiness ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_me_readiness_correct_pct_and_sort():
    """Readiness pct is correct; met requirements appear last (sorted unmet first)."""
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    with tenant_context(tenant.id):
        # Meet SQL (core, min_level=2) — not Python
        SkillAssertion.objects.create(
            tenant=tenant, membership=membership, skill=sql_skill, level=3, skill_version=1
        )

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/me/readiness/?target={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    # 1 of 2 core met → 50%
    assert body["readiness_pct"] == 50
    requirements = body["requirements"]
    assert len(requirements) == 3

    # Unmet requirements come first, met last
    statuses = [r["status"] for r in requirements]
    # The last one(s) should be "met"
    met_indices = [i for i, s in enumerate(statuses) if s == "met"]
    unmet_indices = [i for i, s in enumerate(statuses) if s != "met"]
    if met_indices and unmet_indices:
        assert max(unmet_indices) < min(met_indices), "unmet requirements must come before met"


@pytest.mark.django_db
def test_me_readiness_zero_pct_when_no_assertions():
    """No verified assertions → readiness_pct = 0."""
    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/me/readiness/?target={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    assert resp.json()["readiness_pct"] == 0


@pytest.mark.django_db
def test_me_readiness_denied_without_skill_claim_submit():
    """Missing skill.claim.submit → 403."""
    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/me/readiness/?target={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


# ─── team readiness ───────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_team_readiness_lists_snapshots():
    """Team readiness endpoint lists snapshots for the calling member's org scope."""
    from apps.profiles import services
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["report.org.view"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    with tenant_context(tenant.id):
        services.compute_readiness(membership, profile)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/readiness/?job_profile={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 1
    assert results[0]["job_profile"] == str(profile.id)


@pytest.mark.django_db
def test_team_readiness_isolation():
    """Team readiness endpoint does not leak snapshots from tenant B."""
    from apps.profiles import services
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant_a, person_a, mem_a = _seed_tenant("acme", "a@acme.test", ["report.org.view"])
    tenant_b, person_b, mem_b = _seed_tenant("northwind", "b@nw.test", ["report.org.view"])

    profile_a, sql_a, python_a, dbt_a = _seed_profile(tenant_a)
    with tenant_context(tenant_b.id):
        from apps.skills.models import Skill, SkillDomain

        domain_b = SkillDomain.objects.create(tenant=tenant_b, name="D")
        Skill.objects.create(tenant=tenant_b, domain=domain_b, name="S", slug="s-b", version=1)
        track_b = Track.objects.create(tenant=tenant_b, name="T")
        profile_b = JobProfile.objects.create(
            tenant=tenant_b, track=track_b, grade=1, title="B-Profile"
        )

    with tenant_context(tenant_a.id):
        services.compute_readiness(mem_a, profile_a)
    with tenant_context(tenant_b.id):
        services.compute_readiness(mem_b, profile_b)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/readiness/?job_profile={profile_a.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    for row in resp.json()["results"]:
        assert row["job_profile"] == str(profile_a.id)


@pytest.mark.django_db
def test_team_readiness_denied_without_report_org_view():
    """Missing report.org.view → 403 on team readiness endpoint."""
    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/readiness/?job_profile={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


# ─── heatmap ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_heatmap_shape_members_x_core_reqs():
    """Heatmap is members (rows) × core requirements (columns)."""
    from apps.identity.models import OrgUnit
    from apps.profiles import services
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["report.org.view"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    with tenant_context(tenant.id):
        org_unit = OrgUnit.objects.create(tenant=tenant, name="Engineering", path="/eng")
        membership.org_unit = org_unit
        membership.save()
        services.compute_readiness(membership, profile)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/heatmap/?org_unit={org_unit.id}&job_profile={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "columns" in body  # core requirement skill names
    assert "rows" in body  # member rows
    # 2 core requirements → 2 columns
    assert len(body["columns"]) == 2
    # 1 member → 1 row
    assert len(body["rows"]) == 1
    row = body["rows"][0]
    assert "display_name" in row
    assert "cells" in row
    assert len(row["cells"]) == 2
    for cell in row["cells"]:
        assert "met" in cell


@pytest.mark.django_db
def test_heatmap_denied_without_report_org_view():
    """Missing report.org.view → 403 on heatmap endpoint."""
    from apps.identity.models import OrgUnit
    from core.context import tenant_context

    tenant, person, membership = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    with tenant_context(tenant.id):
        org_unit = OrgUnit.objects.create(tenant=tenant, name="Engineering", path="/eng")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/profiles/heatmap/?org_unit={org_unit.id}&job_profile={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_heatmap_subtree_scoped():
    """Heatmap only returns members in the specified org_unit subtree."""
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, OrgUnit
    from apps.profiles import services
    from core.context import tenant_context

    Person = get_user_model()
    tenant, person_a, mem_a = _seed_tenant("acme", "a@acme.test", ["report.org.view"])
    profile, sql_skill, python_skill, dbt_skill = _seed_profile(tenant)

    with tenant_context(tenant.id):
        # eng org unit → mem_a belongs here
        eng = OrgUnit.objects.create(tenant=tenant, name="Engineering", path="/eng")
        # sales org unit → person_b belongs here
        sales = OrgUnit.objects.create(tenant=tenant, name="Sales", path="/sales")

        mem_a.org_unit = eng
        mem_a.save()

        person_b = Person.objects.create_user(
            email="b@acme.test", display_name="B", password="pw-12345"
        )
        mem_b = Membership.objects.create(
            person=person_b, tenant=tenant, status="active", org_unit=sales
        )

        services.compute_readiness(mem_a, profile)
        services.compute_readiness(mem_b, profile)

    client = APIClient()
    token = _login(client, "a@acme.test")
    # Request heatmap scoped to /eng — should only return mem_a
    resp = client.get(
        f"/api/profiles/heatmap/?org_unit={eng.id}&job_profile={profile.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["display_name"] == person_a.display_name
