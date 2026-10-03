"""Resource library CRUD: the read/write capability split, filters, archiving, isolation."""

from __future__ import annotations

import pytest

from apps.learning.tests.conftest import LEARNER_CAPS, make_member, make_resource

URL = "/api/learning/resources/"

pytestmark = pytest.mark.django_db


def _payload(catalog, **overrides):
    body = {
        "title": "Intermediate Python for Data",
        "kind": "course",
        "module_count": 6,
        "duration_minutes": 240,
        "status": "published",
        "skills": [{"skill": str(catalog["python"].id), "level": 2}],
    }
    body.update(overrides)
    return body


def test_editor_creates_resource_with_skill_links_and_it_is_audited(editor, skills):
    from apps.learning.models import LearningResource
    from core.models import AuditLog

    resp = editor.client().post(URL, _payload(skills), format="json")

    assert resp.status_code == 201, resp.json()
    body = resp.json()
    assert body["skills"] == [
        {"skill": str(skills["python"].id), "skill_name": "PYTHON", "level": 2}
    ]
    resource = LearningResource.all_tenants.get(id=body["id"])
    assert resource.tenant_id == editor.tenant.id
    assert AuditLog.objects.filter(action="resource.create", resource_id=resource.id).exists()


def test_create_is_idempotent_with_an_idempotency_key(editor, skills):
    from apps.learning.models import LearningResource

    client = editor.client()
    first = client.post(URL, _payload(skills), format="json", HTTP_IDEMPOTENCY_KEY="k1")
    again = client.post(URL, _payload(skills), format="json", HTTP_IDEMPOTENCY_KEY="k1")

    assert first.json()["id"] == again.json()["id"]
    assert LearningResource.all_tenants.count() == 1


def test_update_replaces_skill_links(editor, skills):
    resource = make_resource(editor.tenant, "dbt Fundamentals", [(skills["dbt"], 1)])

    resp = editor.client().patch(
        f"{URL}{resource.id}/",
        {
            "skills": [
                {"skill": str(skills["sql"].id), "level": 2},
                {"skill": str(skills["dbt"].id), "level": 2},
            ]
        },
        format="json",
    )

    assert resp.status_code == 200, resp.json()
    assert {(s["skill"], s["level"]) for s in resp.json()["skills"]} == {
        (str(skills["sql"].id), 2),
        (str(skills["dbt"].id), 2),
    }


@pytest.mark.parametrize(
    "links",
    [[("python", 0)], [("python", 6)], [("python", 1), ("python", 2)]],
    ids=["level-too-low", "level-too-high", "duplicate-skill"],
)
def test_invalid_skill_links_are_rejected(editor, skills, links):
    body = _payload(skills, skills=[{"skill": str(skills[s].id), "level": lvl} for s, lvl in links])

    resp = editor.client().post(URL, body, format="json")

    assert resp.status_code == 400
    assert "skills" in resp.json()["error"]["detail"]


def test_another_tenants_skill_cannot_be_linked(editor, globex, skills):
    from apps.skills.models import Skill, SkillDomain

    domain = SkillDomain.objects.create(tenant=globex, name="Private")
    private = Skill.objects.create(tenant=globex, domain=domain, name="Secret", slug="secret")

    resp = editor.client().post(
        URL, _payload(skills, skills=[{"skill": str(private.id), "level": 1}]), format="json"
    )

    assert resp.status_code == 400
    assert resp.json()["error"]["detail"]["skills"] == [{"skill": ["Unknown skill."]}]


def test_destroy_archives_instead_of_deleting(editor, skills):
    from apps.learning.models import LearningResource
    from core.models import AuditLog

    resource = make_resource(editor.tenant, "Kafka in 30 Minutes", [])

    resp = editor.client().delete(f"{URL}{resource.id}/")

    assert resp.status_code == 204
    resource = LearningResource.all_tenants.get(id=resource.id)
    assert resource.status == "archived"
    assert AuditLog.objects.filter(action="resource.archive", resource_id=resource.id).exists()


@pytest.mark.parametrize("method", ["post", "patch", "delete"])
def test_learner_cannot_write(learner, skills, method):
    resource = make_resource(learner.tenant, "Existing", [])
    client = learner.client()

    if method == "post":
        resp = client.post(URL, _payload(skills), format="json")
    elif method == "patch":
        resp = client.patch(f"{URL}{resource.id}/", {"title": "Hijacked"}, format="json")
    else:
        resp = client.delete(f"{URL}{resource.id}/")

    assert resp.status_code == 403


def test_member_without_directory_view_cannot_read(acme):
    member = make_member(acme, "nocaps@acme.test", ["skill.claim.submit"])

    assert member.client().get(URL).status_code == 403


def test_learners_see_only_published_editors_see_everything(learner, editor, skills):
    make_resource(learner.tenant, "Live", [], status="published")
    make_resource(learner.tenant, "Draft", [], status="draft")
    make_resource(learner.tenant, "Old", [], status="archived")

    learner_titles = {r["title"] for r in learner.client().get(URL).json()["results"]}
    editor_titles = {r["title"] for r in editor.client().get(URL).json()["results"]}
    drafts = {r["title"] for r in editor.client().get(URL, {"status": "draft"}).json()["results"]}

    assert learner_titles == {"Live"}
    assert editor_titles == {"Live", "Draft", "Old"}
    assert drafts == {"Draft"}


def test_learner_cannot_retrieve_a_draft(learner):
    draft = make_resource(learner.tenant, "Draft", [], status="draft")

    assert learner.client().get(f"{URL}{draft.id}/").status_code == 404


def test_filters_by_skill_kind_and_title(learner, skills):
    make_resource(learner.tenant, "Python course", [(skills["python"], 2)], kind="course")
    make_resource(learner.tenant, "Python video", [(skills["python"], 1)], kind="video")
    make_resource(learner.tenant, "SQL article", [(skills["sql"], 2)], kind="article")
    client = learner.client()

    def titles(**params):
        return {r["title"] for r in client.get(URL, params).json()["results"]}

    assert titles(skill=str(skills["python"].id)) == {"Python course", "Python video"}
    assert titles(kind="video") == {"Python video"}
    assert titles(q="sql") == {"SQL article"}


def test_resources_are_tenant_isolated(learner, editor, globex, skills):
    other = make_resource(globex, "Globex only", [(skills["sql"], 1)])
    make_resource(learner.tenant, "Acme only", [(skills["sql"], 1)])
    make_member(globex, "g@globex.test", LEARNER_CAPS)

    titles = {r["title"] for r in learner.client().get(URL).json()["results"]}
    editor_client = editor.client()

    assert titles == {"Acme only"}
    assert editor_client.get(f"{URL}{other.id}/").status_code == 404
    assert (
        editor_client.patch(f"{URL}{other.id}/", {"title": "x"}, format="json").status_code == 404
    )
    assert editor_client.delete(f"{URL}{other.id}/").status_code == 404
