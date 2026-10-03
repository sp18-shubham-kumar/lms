"""
Job-profile versioning + requirement editor contract (P2-R5, P2-R9, P2-R10).

- Published/retired profiles are never mutated in place (409), drafts are.
- POST /new-version/ opens the next draft, copies requirements, retains the prior version.
- GET /requirements/ lists a profile's requirements for the editor.
- Requirement skills are limited to globals + the caller's tenant.
- Readiness is pinned to the version it was computed against.
"""

import pytest
from rest_framework.test import APIClient

from apps.profiles.tests.test_readiness_api import _login, _seed_profile, _seed_tenant

EDITOR_CAPS = ["jobprofile.edit", "directory.view", "skill.claim.submit"]


@pytest.fixture
def editor():
    """A tenant whose admin can edit profiles, with a published 2-core + 1-supporting profile."""
    tenant, person, membership = _seed_tenant("acme", "a@acme.test", EDITOR_CAPS)
    profile, sql, python, dbt = _seed_profile(tenant)
    client = APIClient()
    token = _login(client, "a@acme.test")
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}", HTTP_X_TENANT_ID=str(tenant.id))
    return {
        "tenant": tenant,
        "person": person,
        "membership": membership,
        "profile": profile,
        "skills": {"sql": sql, "python": python, "dbt": dbt},
        "client": client,
    }


def _url(profile_id, suffix=""):
    return f"/api/profiles/job-profiles/{profile_id}/{suffix}"


def _draft(editor):
    from apps.profiles.models import JobProfile, Track
    from core.context import tenant_context

    with tenant_context(editor["tenant"].id):
        track = Track.objects.first()
        return JobProfile.objects.create(
            tenant=editor["tenant"], track=track, grade=3, title="Data Engineer L3"
        )


# ─── Requirements list ───────────────────────────────────────────────────────


@pytest.mark.django_db
def test_requirements_list_names_each_skill(editor):
    resp = editor["client"].get(_url(editor["profile"].id, "requirements/"))
    assert resp.status_code == 200
    body = resp.json()
    assert [r["skill_name"] for r in body] == ["Python", "SQL", "dbt"]
    assert {r["criticality"] for r in body} == {"core", "supporting"}


@pytest.mark.django_db
def test_requirements_list_readable_with_directory_view_only():
    tenant, _, _ = _seed_tenant("acme", "v@acme.test", ["directory.view"])
    profile, *_ = _seed_profile(tenant)
    client = APIClient()
    token = _login(client, "v@acme.test")
    resp = client.get(
        _url(profile.id, "requirements/"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 200
    assert len(resp.json()) == 3


@pytest.mark.django_db
def test_requirements_list_isolated_from_other_tenants(editor):
    other, _, _ = _seed_tenant("globex", "g@globex.test", ["directory.view"])
    client = APIClient()
    token = _login(client, "g@globex.test")
    resp = client.get(
        _url(editor["profile"].id, "requirements/"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(other.id),
    )
    assert resp.status_code == 404


# ─── Published profiles are immutable ────────────────────────────────────────


@pytest.mark.django_db
def test_published_profile_rejects_requirement_add(editor):
    from apps.profiles.models import ProfileRequirement
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(editor["tenant"].id):
        domain = SkillDomain.objects.first()
        spark = Skill.objects.create(
            tenant=editor["tenant"], domain=domain, name="Spark", slug="spark", version=1
        )
    resp = editor["client"].post(
        _url(editor["profile"].id, "requirements/"),
        {"skill": str(spark.id), "min_level": 2, "criticality": "core"},
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "profile_not_editable"
    with tenant_context(editor["tenant"].id):
        assert ProfileRequirement.objects.filter(job_profile=editor["profile"]).count() == 3


@pytest.mark.django_db
def test_published_profile_rejects_requirement_remove(editor):
    from apps.profiles.models import ProfileRequirement
    from core.context import tenant_context

    with tenant_context(editor["tenant"].id):
        req = ProfileRequirement.objects.filter(job_profile=editor["profile"]).first()
    resp = editor["client"].delete(_url(editor["profile"].id, f"requirements/{req.id}/"))
    assert resp.status_code == 409
    with tenant_context(editor["tenant"].id):
        assert ProfileRequirement.objects.filter(id=req.id).exists()


@pytest.mark.django_db
def test_published_profile_rejects_in_place_edit(editor):
    resp = editor["client"].patch(_url(editor["profile"].id), {"title": "Renamed"}, format="json")
    assert resp.status_code == 409
    editor["profile"].refresh_from_db()
    assert editor["profile"].title == "Data Engineer L2"


@pytest.mark.django_db
def test_draft_profile_accepts_edits(editor):
    draft = _draft(editor)
    resp = editor["client"].patch(_url(draft.id), {"title": "DE L3"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["title"] == "DE L3"


@pytest.mark.django_db
def test_retired_profile_cannot_be_republished(editor):
    editor["profile"].status = "retired"
    editor["profile"].save()
    resp = editor["client"].post(_url(editor["profile"].id, "publish/"))
    assert resp.status_code == 409


@pytest.mark.django_db
def test_publishing_a_published_profile_is_a_noop(editor):
    from core.models import AuditLog

    resp = editor["client"].post(_url(editor["profile"].id, "publish/"))
    assert resp.status_code == 200
    assert resp.json()["status"] == "published"
    assert not AuditLog.objects.filter(action="jobprofile.publish").exists()


# ─── New version ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_new_version_copies_requirements_and_keeps_prior(editor):
    from apps.profiles.models import JobProfile, ProfileRequirement
    from core.context import tenant_context
    from core.models import AuditLog

    resp = editor["client"].post(_url(editor["profile"].id, "new-version/"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["version"] == 2
    assert body["status"] == "draft"
    assert body["title"] == "Data Engineer L2"

    with tenant_context(editor["tenant"].id):
        assert ProfileRequirement.objects.filter(job_profile_id=body["id"]).count() == 3
        v1 = JobProfile.objects.get(id=editor["profile"].id)
    assert (v1.version, v1.status) == (1, "published")
    assert AuditLog.objects.filter(action="jobprofile.new_version").exists()


@pytest.mark.django_db
def test_new_version_allows_only_one_open_draft(editor):
    first = editor["client"].post(_url(editor["profile"].id, "new-version/"))
    assert first.status_code == 201
    second = editor["client"].post(_url(editor["profile"].id, "new-version/"))
    assert second.status_code == 409


@pytest.mark.django_db
def test_new_version_of_a_draft_is_rejected(editor):
    draft = _draft(editor)
    resp = editor["client"].post(_url(draft.id, "new-version/"))
    assert resp.status_code == 409


@pytest.mark.django_db
def test_new_version_denied_without_jobprofile_edit():
    tenant, _, _ = _seed_tenant("acme", "v@acme.test", ["directory.view"])
    profile, *_ = _seed_profile(tenant)
    client = APIClient()
    token = _login(client, "v@acme.test")
    resp = client.post(
        _url(profile.id, "new-version/"),
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403


# ─── Requirement validation ──────────────────────────────────────────────────


@pytest.mark.django_db
def test_requirement_rejects_another_tenants_skill(editor):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    other, _, _ = _seed_tenant("globex", "g@globex.test", [])
    with tenant_context(other.id):
        domain = SkillDomain.objects.create(tenant=other, name="Secret")
        secret = Skill.objects.create(
            tenant=other, domain=domain, name="Globex Secret", slug="secret", version=1
        )
    draft = _draft(editor)
    resp = editor["client"].post(
        _url(draft.id, "requirements/"),
        {"skill": str(secret.id), "min_level": 2, "criticality": "core"},
        format="json",
    )
    assert resp.status_code == 400
    assert "Globex Secret" not in resp.content.decode()


@pytest.mark.django_db
def test_requirement_accepts_global_skill(editor):
    from apps.skills.models import Skill, SkillDomain

    domain = SkillDomain.objects.create(tenant=None, name="Global")
    shared = Skill.objects.create(
        tenant=None, domain=domain, name="Shared", slug="shared", version=1
    )
    draft = _draft(editor)
    resp = editor["client"].post(
        _url(draft.id, "requirements/"),
        {"skill": str(shared.id), "min_level": 2, "criticality": "core"},
        format="json",
    )
    assert resp.status_code == 201
    assert resp.json()["skill_name"] == "Shared"


@pytest.mark.django_db
@pytest.mark.parametrize("level", [0, 6])
def test_requirement_level_must_be_on_the_rubric(editor, level):
    draft = _draft(editor)
    resp = editor["client"].post(
        _url(draft.id, "requirements/"),
        {"skill": str(editor["skills"]["sql"].id), "min_level": level, "criticality": "core"},
        format="json",
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_duplicate_requirement_is_a_conflict(editor):
    draft = _draft(editor)
    payload = {"skill": str(editor["skills"]["sql"].id), "min_level": 2, "criticality": "core"}
    assert (
        editor["client"].post(_url(draft.id, "requirements/"), payload, format="json").status_code
        == 201
    )
    resp = editor["client"].post(_url(draft.id, "requirements/"), payload, format="json")
    assert resp.status_code == 409


# ─── List filters ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_list_filters_by_status(editor):
    _draft(editor)
    resp = editor["client"].get("/api/profiles/job-profiles/?status=published")
    assert resp.status_code == 200
    assert [p["title"] for p in resp.json()["results"]] == ["Data Engineer L2"]


# ─── Readiness is pinned to a version ────────────────────────────────────────


@pytest.mark.django_db
def test_readiness_against_v1_unchanged_by_v2_draft(editor):
    """Adding a requirement to v2 doesn't move a learner's readiness against v1."""
    from apps.profiles.models import ReadinessSnapshot
    from apps.skills.models import Skill, SkillAssertion, SkillDomain
    from core.context import tenant_context

    tenant, membership = editor["tenant"], editor["membership"]
    with tenant_context(tenant.id):
        for key in ("sql", "python"):
            SkillAssertion.objects.create(
                tenant=tenant,
                membership=membership,
                skill=editor["skills"][key],
                level=3,
                skill_version=1,
            )
        spark = Skill.objects.create(
            tenant=tenant,
            domain=SkillDomain.objects.first(),
            name="Spark",
            slug="spark",
            version=1,
        )

    client = editor["client"]
    v1_id = editor["profile"].id
    assert client.get(f"/api/profiles/me/readiness/?target={v1_id}").json()["readiness_pct"] == 100

    v2_id = client.post(_url(v1_id, "new-version/")).json()["id"]
    added = client.post(
        _url(v2_id, "requirements/"),
        {"skill": str(spark.id), "min_level": 2, "criticality": "core"},
        format="json",
    )
    assert added.status_code == 201

    v1 = client.get(f"/api/profiles/me/readiness/?target={v1_id}").json()
    v2 = client.get(f"/api/profiles/me/readiness/?target={v2_id}").json()
    assert (v1["met"], v1["total"], v1["readiness_pct"]) == (2, 2, 100)
    assert (v2["met"], v2["total"], v2["readiness_pct"]) == (2, 3, 66)
    spark_row = next(r for r in v2["requirements"] if r["skill_name"] == "Spark")
    assert spark_row["status"] == "not_started"
    assert "Spark" not in {r["skill_name"] for r in v1["requirements"]}

    with tenant_context(tenant.id):
        versions = dict(
            ReadinessSnapshot.objects.filter(membership=membership).values_list(
                "job_profile_id", "job_profile_version"
            )
        )
    assert versions[v1_id] == 1
    assert str(v2_id) in {str(k) for k in versions}
    assert sorted(versions.values()) == [1, 2]
