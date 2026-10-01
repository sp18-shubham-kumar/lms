"""
Tests for Task 17: Track/JobProfile CRUD + publish endpoints.
- Create track + profile + requirement as admin
- Isolation: tenant A can't see B's profiles
- Non-admin write → 403
- Publish bumps status
- Editing published → new version
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


def _seed_skill(tenant):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name="Engineering")
        return Skill.objects.create(tenant=tenant, domain=domain, name="SQL", slug="sql", version=1)


# ─── Track CRUD ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_create_track():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/tracks/",
        {"name": "Backend"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    assert resp.json()["name"] == "Backend"


@pytest.mark.django_db
def test_create_track_denied_without_jobprofile_edit():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/tracks/",
        {"name": "Backend"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_track_list_isolation():
    """Tenant A cannot see Tenant B's tracks."""
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant_a, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "jobprofile.edit"])
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view", "jobprofile.edit"])

    with tenant_context(tenant_a.id):
        Track.objects.create(tenant=tenant_a, name="A-Track")
    with tenant_context(tenant_b.id):
        Track.objects.create(tenant=tenant_b, name="B-Track")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/profiles/tracks/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    names = [r["name"] for r in resp.json()["results"]]
    assert "A-Track" in names
    assert "B-Track" not in names


# ─── JobProfile CRUD ──────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_create_job_profile():
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/job-profiles/",
        {"track": str(track.id), "grade": 1, "title": "Junior Engineer"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "draft"
    assert body["version"] == 1
    assert body["title"] == "Junior Engineer"


@pytest.mark.django_db
def test_create_job_profile_denied_without_jobprofile_edit():
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/job-profiles/",
        {"track": str(track.id), "grade": 1, "title": "Junior Engineer"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_job_profile_list_isolation():
    """Tenant A cannot see Tenant B's job profiles."""
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant_a, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "jobprofile.edit"])
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view", "jobprofile.edit"])

    with tenant_context(tenant_a.id):
        track_a = Track.objects.create(tenant=tenant_a, name="A-Track")
        JobProfile.objects.create(tenant=tenant_a, track=track_a, grade=1, title="A-Profile")
    with tenant_context(tenant_b.id):
        track_b = Track.objects.create(tenant=tenant_b, name="B-Track")
        JobProfile.objects.create(tenant=tenant_b, track=track_b, grade=1, title="B-Profile")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/profiles/job-profiles/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    titles = [r["title"] for r in resp.json()["results"]]
    assert "A-Profile" in titles
    assert "B-Profile" not in titles


# ─── Requirements nested endpoint ─────────────────────────────────────────────


@pytest.mark.django_db
def test_add_requirement_to_job_profile():
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    skill = _seed_skill(tenant)

    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    # Create profile
    resp = client.post(
        "/api/profiles/job-profiles/",
        {"track": str(track.id), "grade": 1, "title": "L1"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    profile_id = resp.json()["id"]

    # Add requirement
    resp = client.post(
        f"/api/profiles/job-profiles/{profile_id}/requirements/",
        {"skill": str(skill.id), "min_level": 2, "criticality": "core"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["criticality"] == "core"
    assert body["min_level"] == 2


@pytest.mark.django_db
def test_delete_requirement_from_job_profile():
    from apps.profiles.models import ProfileRequirement, Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    skill = _seed_skill(tenant)

    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/job-profiles/",
        {"track": str(track.id), "grade": 1, "title": "L1"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    profile_id = resp.json()["id"]

    resp = client.post(
        f"/api/profiles/job-profiles/{profile_id}/requirements/",
        {"skill": str(skill.id), "min_level": 2, "criticality": "core"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    req_id = resp.json()["id"]

    resp = client.delete(
        f"/api/profiles/job-profiles/{profile_id}/requirements/{req_id}/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 204

    with tenant_context(tenant.id):
        assert ProfileRequirement.objects.filter(id=req_id).count() == 0


# ─── Publish ─────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_publish_job_profile():
    from apps.profiles.models import Track
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/profiles/job-profiles/",
        {"track": str(track.id), "grade": 1, "title": "L1"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    profile_id = resp.json()["id"]

    resp = client.post(
        f"/api/profiles/job-profiles/{profile_id}/publish/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert AuditLog.objects.filter(action="jobprofile.publish").exists()


@pytest.mark.django_db
def test_publish_denied_without_jobprofile_edit():
    from apps.profiles.models import Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        from apps.profiles.models import JobProfile

        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="L1")

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        f"/api/profiles/job-profiles/{profile.id}/publish/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


@pytest.mark.django_db
def test_editing_published_job_profile_creates_new_version():
    """Editing a published profile creates a new version 2 draft; v1 is retained."""
    from apps.profiles import services as profile_services
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant, person, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")
        profile = JobProfile.objects.create(tenant=tenant, track=track, grade=1, title="L1")
        profile_services.publish_job_profile(profile, person)

        new_draft = profile_services.new_version_from_profile(profile, person)
        assert new_draft.version == 2
        assert new_draft.status == "draft"

        # v1 is retained unchanged
        v1 = JobProfile.all_tenants.get(id=profile.id)
        assert v1.version == 1
        assert v1.status == "published"


@pytest.mark.django_db
def test_job_profile_idempotent_create():
    """Create with Idempotency-Key twice → same id, single row."""
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["jobprofile.edit"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Backend")

    client = APIClient()
    token = _login(client, "a@acme.test")
    headers = {
        "HTTP_AUTHORIZATION": f"Bearer {token}",
        "HTTP_X_TENANT_ID": str(tenant.id),
        "HTTP_IDEMPOTENCY_KEY": "profile-create-1",
    }
    payload = {"track": str(track.id), "grade": 1, "title": "L1"}
    r1 = client.post("/api/profiles/job-profiles/", payload, format="json", **headers)
    r2 = client.post("/api/profiles/job-profiles/", payload, format="json", **headers)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    with tenant_context(tenant.id):
        assert JobProfile.objects.count() == 1


@pytest.mark.django_db
def test_job_profile_list_allowed_with_directory_view():
    """A learner (directory.view only) can browse job profiles to pick a target grade."""
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Data")
        JobProfile.objects.create(
            tenant=tenant, track=track, grade=2, title="DE L2", status="published"
        )

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/profiles/job-profiles/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    titles = [p["title"] for p in resp.json()["results"]]
    assert "DE L2" in titles
