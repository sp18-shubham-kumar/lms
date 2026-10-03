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


def _add_member(tenant, email, display_name=None, org_unit=None):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(
        email=email, display_name=display_name or email, password="pw-12345"
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(
            person=person, tenant=tenant, status="active", org_unit=org_unit
        )
    return person, membership


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


def _get(client, url, email, tenant):
    token = _login(client, email)
    return client.get(url, HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant.id))


def _skill(slug="sql"):
    from apps.skills.models import Skill, SkillDomain

    domain = SkillDomain.objects.create(tenant=None, name=f"Domain {slug}")
    return Skill.objects.create(
        tenant=None, domain=domain, name=slug.upper(), slug=slug, status="published"
    )


@pytest.mark.django_db
def test_profile_shows_declared_and_verified_skills_with_tenant_override_name():
    from django.utils import timezone

    from apps.identity.models import OrgUnit
    from apps.skills.models import SelfDeclaredSkill, SkillAssertion, TenantSkillOverride
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["directory.view"])
    with tenant_context(tenant.id):
        unit = OrgUnit.objects.create(tenant=tenant, name="Data", path="data")
    person, membership = _add_member(tenant, "bob@acme.test", "Bob", org_unit=unit)
    sql, python = _skill("sql"), _skill("python")
    with tenant_context(tenant.id):
        TenantSkillOverride.objects.create(tenant=tenant, skill=sql, name="Acme SQL")
        SelfDeclaredSkill.objects.create(
            tenant=tenant, membership=membership, skill=sql, level=2, note="daily"
        )
        SkillAssertion.objects.create(
            tenant=tenant,
            membership=membership,
            skill=python,
            level=3,
            skill_version=1,
            verified_at=timezone.now(),
        )

    resp = _get(APIClient(), f"/api/identity/people/{person.id}/", "admin@acme.test", tenant)

    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Bob"
    assert body["org_unit"]["name"] == "Data"
    assert body["declared"] == [
        {"skill_id": str(sql.id), "skill_name": "Acme SQL", "level": 2, "note": "daily"}
    ]
    assert [(v["skill_name"], v["level"]) for v in body["verified"]] == [("PYTHON", 3)]


@pytest.mark.django_db
def test_member_can_read_own_profile_without_directory_view():
    tenant, person, _ = _seed_tenant("acme", "me@acme.test", [])

    resp = _get(APIClient(), f"/api/identity/people/{person.id}/", "me@acme.test", tenant)

    assert resp.status_code == 200
    assert resp.json()["email"] == "me@acme.test"


@pytest.mark.django_db
def test_reading_someone_else_requires_directory_view():
    tenant, _, _ = _seed_tenant("acme", "me@acme.test", [])
    other, _ = _add_member(tenant, "other@acme.test")

    resp = _get(APIClient(), f"/api/identity/people/{other.id}/", "me@acme.test", tenant)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_person_from_another_tenant_is_not_found():
    tenant_a, _, _ = _seed_tenant("acme", "admin@acme.test", ["directory.view"])
    tenant_b, outsider, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])

    resp = _get(APIClient(), f"/api/identity/people/{outsider.id}/", "admin@acme.test", tenant_a)

    assert resp.status_code == 404


@pytest.mark.django_db
def test_readiness_hidden_from_others_without_report_capability():
    from django.utils import timezone

    from apps.profiles.models import JobProfile, ReadinessSnapshot, Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "viewer@acme.test", ["directory.view"])
    person, membership = _add_member(tenant, "bob@acme.test")
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Data")
        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="DE L1")
        ReadinessSnapshot.objects.create(
            tenant=tenant,
            membership=membership,
            job_profile=profile,
            met=1,
            total=4,
            job_profile_version=1,
            computed_at=timezone.now(),
        )

    other = _get(APIClient(), f"/api/identity/people/{person.id}/", "viewer@acme.test", tenant)
    own = _get(APIClient(), f"/api/identity/people/{person.id}/", "bob@acme.test", tenant)

    assert other.json()["readiness"] == []
    assert own.json()["readiness"][0]["job_profile_name"] == "DE L1"
    assert own.json()["readiness"][0]["readiness_pct"] == 25


@pytest.mark.django_db
def test_people_search_matches_name_or_email():
    tenant, _, _ = _seed_tenant("acme", "admin@acme.test", ["directory.view"])
    _add_member(tenant, "priya@acme.test", "Priya Nair")
    _add_member(tenant, "sam@acme.test", "Sam Okafor")

    by_name = _get(APIClient(), "/api/identity/people/?q=nair", "admin@acme.test", tenant)
    by_email = _get(APIClient(), "/api/identity/people/?q=SAM@", "admin@acme.test", tenant)

    assert [r["display_name"] for r in by_name.json()["results"]] == ["Priya Nair"]
    assert [r["display_name"] for r in by_email.json()["results"]] == ["Sam Okafor"]
