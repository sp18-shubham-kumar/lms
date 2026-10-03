"""Learner progress: transitions, guard rails, ownership, isolation, and no readiness side effects."""

from __future__ import annotations

import pytest

from apps.learning.tests.conftest import make_member, make_resource

URL = "/api/learning/me/progress/"

pytestmark = pytest.mark.django_db


@pytest.fixture
def course(acme, skills):
    return make_resource(acme, "Intermediate Python for Data", [(skills["python"], 2)])


def _start(client, resource):
    return client.post(URL, {"resource": str(resource.id)}, format="json")


def test_start_creates_in_progress_row_then_is_idempotent(learner, course):
    from core.models import AuditLog

    client = learner.client()
    first = _start(client, course)
    again = _start(client, course)

    assert first.status_code == 201, first.json()
    assert again.status_code == 200
    assert first.json()["id"] == again.json()["id"]
    body = first.json()
    assert body["status"] == "in_progress"
    assert body["completed_modules"] == 0
    assert body["started_at"] is not None
    assert body["resource_detail"]["title"] == "Intermediate Python for Data"
    assert AuditLog.objects.filter(action="learning.progress.start").count() == 1


def test_advancing_modules_then_reaching_the_total_completes(learner, course):
    from core.models import AuditLog

    client = learner.client()
    progress_id = _start(client, course).json()["id"]

    step = client.patch(f"{URL}{progress_id}/", {"completed_modules": 2}, format="json")
    assert step.status_code == 200, step.json()
    assert (step.json()["status"], step.json()["completed_modules"]) == ("in_progress", 2)

    done = client.patch(f"{URL}{progress_id}/", {"completed_modules": 4}, format="json")
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"] is not None
    actions = set(AuditLog.objects.values_list("action", flat=True))
    assert {"learning.progress.update", "learning.progress.complete"} <= actions


def test_status_completed_fills_every_module(learner, course):
    client = learner.client()
    progress_id = _start(client, course).json()["id"]

    resp = client.patch(f"{URL}{progress_id}/", {"status": "completed"}, format="json")

    assert resp.json()["status"] == "completed"
    assert resp.json()["completed_modules"] == 4


def test_reopening_a_completed_resource_keeps_it_short_of_the_end(learner, course):
    client = learner.client()
    progress_id = _start(client, course).json()["id"]
    client.patch(f"{URL}{progress_id}/", {"status": "completed"}, format="json")

    resp = client.patch(f"{URL}{progress_id}/", {"status": "in_progress"}, format="json")

    assert resp.json()["status"] == "in_progress"
    assert resp.json()["completed_modules"] == 3
    assert resp.json()["completed_at"] is None


def test_more_modules_than_the_resource_has_is_rejected(learner, course):
    client = learner.client()
    progress_id = _start(client, course).json()["id"]

    resp = client.patch(f"{URL}{progress_id}/", {"completed_modules": 5}, format="json")

    assert resp.status_code == 400
    assert "completed_modules" in resp.json()["error"]["detail"]


def test_empty_update_is_rejected(learner, course):
    client = learner.client()
    progress_id = _start(client, course).json()["id"]

    assert client.patch(f"{URL}{progress_id}/", {}, format="json").status_code == 400


def test_reset_clears_progress_and_is_audited(learner, course):
    from core.models import AuditLog

    client = learner.client()
    progress_id = _start(client, course).json()["id"]
    client.patch(f"{URL}{progress_id}/", {"completed_modules": 3}, format="json")

    resp = client.patch(f"{URL}{progress_id}/", {"status": "not_started"}, format="json")

    body = resp.json()
    assert (body["status"], body["completed_modules"], body["started_at"]) == (
        "not_started",
        0,
        None,
    )
    assert AuditLog.objects.filter(action="learning.progress.reset").exists()


@pytest.mark.parametrize("status", ["draft", "archived"])
def test_unpublished_resources_cannot_be_started(learner, acme, skills, status):
    resource = make_resource(acme, "Hidden", [(skills["sql"], 2)], status=status)

    resp = _start(learner.client(), resource)

    assert resp.status_code == 400


def test_archived_resource_can_be_reset_but_not_advanced(learner, course):
    from apps.learning.models import LearningResource

    client = learner.client()
    progress_id = _start(client, course).json()["id"]
    LearningResource.all_tenants.filter(id=course.id).update(status="archived")

    advance = client.patch(f"{URL}{progress_id}/", {"completed_modules": 1}, format="json")
    reset = client.patch(f"{URL}{progress_id}/", {"status": "not_started"}, format="json")

    assert advance.status_code == 400
    assert reset.status_code == 200


def test_learner_sees_only_their_own_progress(learner, acme, course):
    peer = make_member(acme, "peer@acme.test", ["directory.view", "skill.claim.submit"])
    peer_progress_id = _start(peer.client(), course).json()["id"]
    own_id = _start(learner.client(), course).json()["id"]

    client = learner.client()
    listed = [row["id"] for row in client.get(URL).json()["results"]]

    assert listed == [own_id]
    assert client.get(f"{URL}{peer_progress_id}/").status_code == 404
    patch = client.patch(f"{URL}{peer_progress_id}/", {"completed_modules": 1}, format="json")
    assert patch.status_code == 404


def test_cannot_start_another_tenants_resource(learner, globex, skills):
    foreign = make_resource(globex, "Globex only", [(skills["sql"], 2)])

    resp = _start(learner.client(), foreign)

    assert resp.status_code == 400
    assert "resource" in resp.json()["error"]["detail"]


def test_progress_does_not_leak_across_tenants(learner, globex, skills):
    outsider = make_member(globex, "outsider@globex.test", ["directory.view", "skill.claim.submit"])
    foreign = make_resource(globex, "Globex only", [(skills["sql"], 2)])
    foreign_id = _start(outsider.client(), foreign).json()["id"]

    client = learner.client()

    assert client.get(URL).json()["results"] == []
    assert client.get(f"{URL}{foreign_id}/").status_code == 404


def test_member_without_skill_claim_submit_cannot_record_progress(acme, course):
    viewer = make_member(acme, "viewer@acme.test", ["directory.view"])
    client = viewer.client()

    assert _start(client, course).status_code == 403
    assert client.get(URL).status_code == 403


def test_put_and_delete_are_not_offered(learner, course):
    client = learner.client()
    progress_id = _start(client, course).json()["id"]

    assert client.put(f"{URL}{progress_id}/", {}, format="json").status_code == 405
    assert client.delete(f"{URL}{progress_id}/").status_code == 405


def test_completing_a_resource_does_not_verify_skills_or_move_readiness(
    learner, acme, skills, course
):
    from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot, Track
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    with tenant_context(acme.id):
        track = Track.objects.create(tenant=acme, name="Data")
        profile = JobProfile.objects.create(
            tenant=acme, track=track, grade=2, title="Data Engineer L2", status="published"
        )
        ProfileRequirement.objects.create(
            tenant=acme,
            job_profile=profile,
            skill=skills["python"],
            min_level=2,
            criticality="core",
        )

    client = learner.client()
    readiness_url = f"/api/profiles/me/readiness/?target={profile.id}"
    before = client.get(readiness_url)
    assert before.status_code == 200, before.json()
    snapshot_before = list(
        ReadinessSnapshot.all_tenants.values("met", "total", "blocking_skill_ids", "computed_at")
    )

    progress_id = _start(client, course).json()["id"]
    client.patch(f"{URL}{progress_id}/", {"status": "completed"}, format="json")

    assert not SkillAssertion.all_tenants.exists()
    assert (
        list(
            ReadinessSnapshot.all_tenants.values(
                "met", "total", "blocking_skill_ids", "computed_at"
            )
        )
        == snapshot_before
    )
    assert client.get(readiness_url).json() == before.json()
