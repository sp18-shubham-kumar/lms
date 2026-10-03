"""Gap-based recommendations: which gaps, which resources, in what order."""

from __future__ import annotations

import pytest

from apps.learning.tests.conftest import make_member, make_resource

URL = "/api/learning/me/recommendations/"

pytestmark = pytest.mark.django_db


def _profile(tenant, requirements):
    """A published profile; ``requirements`` is ``[(skill, min_level, criticality)]``."""
    from apps.profiles.models import JobProfile, ProfileRequirement, Track
    from core.context import tenant_context

    with tenant_context(tenant.id):
        track = Track.objects.create(tenant=tenant, name="Data")
        profile = JobProfile.objects.create(
            tenant=tenant, track=track, grade=2, title="Data Engineer L2", status="published"
        )
        for skill, min_level, criticality in requirements:
            ProfileRequirement.objects.create(
                tenant=tenant,
                job_profile=profile,
                skill=skill,
                min_level=min_level,
                criticality=criticality,
            )
    return profile


def _verify(member, skill, level):
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context

    with tenant_context(member.tenant.id):
        SkillAssertion.objects.create(
            tenant=member.tenant,
            membership=member.membership,
            skill=skill,
            level=level,
            skill_version=1,
        )


def _titles(gap):
    return [row["resource"]["title"] for row in gap["resources"]]


def test_only_unmet_requirements_are_returned_smallest_gap_first(learner, acme, skills):
    profile = _profile(
        acme,
        [
            (skills["sql"], 2, "core"),
            (skills["python"], 3, "core"),
            (skills["dbt"], 1, "supporting"),
        ],
    )
    _verify(learner, skills["sql"], 2)
    _verify(learner, skills["python"], 1)

    resp = learner.client().get(URL, {"target": str(profile.id)})

    assert resp.status_code == 200, resp.json()
    gaps = resp.json()["gaps"]
    assert [(g["skill_name"], g["current_level"], g["min_level"]) for g in gaps] == [
        ("DBT", None, 1),
        ("PYTHON", 1, 3),
    ]
    assert gaps[0]["criticality"] == "supporting"


def test_resources_at_or_below_the_current_level_and_unpublished_are_excluded(
    learner, acme, skills
):
    profile = _profile(acme, [(skills["python"], 3, "core")])
    _verify(learner, skills["python"], 1)
    make_resource(acme, "Python Basics", [(skills["python"], 1)])
    make_resource(acme, "Intermediate Python", [(skills["python"], 2)])
    make_resource(acme, "Draft Python", [(skills["python"], 2)], status="draft")
    make_resource(acme, "Archived Python", [(skills["python"], 3)], status="archived")

    gap = learner.client().get(URL, {"target": str(profile.id)}).json()["gaps"][0]

    assert _titles(gap) == ["Intermediate Python"]
    assert gap["resources"][0]["target_level"] == 2


def test_in_gap_resources_rank_before_overshoot_and_completed_go_last(learner, acme, skills):
    from apps.learning.services import start_progress, update_progress

    profile = _profile(acme, [(skills["python"], 3, "core")])
    make_resource(acme, "Expert Python", [(skills["python"], 5)])
    make_resource(acme, "Python Testing", [(skills["python"], 3)])
    make_resource(acme, "Intermediate Python", [(skills["python"], 2)])
    done = make_resource(acme, "Python Basics", [(skills["python"], 1)])
    progress, _ = start_progress(learner.membership, done, learner.person)
    update_progress(progress, learner.person, status="completed")

    gap = learner.client().get(URL, {"target": str(profile.id)}).json()["gaps"][0]

    assert _titles(gap) == [
        "Intermediate Python",
        "Python Testing",
        "Expert Python",
        "Python Basics",
    ]
    assert gap["resources"][-1]["progress"]["status"] == "completed"
    assert gap["resources"][0]["progress"] is None


def test_a_resource_linked_to_two_gap_skills_appears_under_both(learner, acme, skills):
    profile = _profile(acme, [(skills["sql"], 2, "core"), (skills["dbt"], 1, "core")])
    make_resource(acme, "dbt Fundamentals", [(skills["dbt"], 1), (skills["sql"], 2)])

    gaps = learner.client().get(URL, {"target": str(profile.id)}).json()["gaps"]

    assert [_titles(g) for g in gaps] == [["dbt Fundamentals"], ["dbt Fundamentals"]]


def test_recommendations_reflect_only_the_callers_progress(learner, acme, skills):
    from apps.learning.services import start_progress

    profile = _profile(acme, [(skills["python"], 2, "core")])
    course = make_resource(acme, "Intermediate Python", [(skills["python"], 2)])
    peer = make_member(acme, "peer@acme.test", ["directory.view", "skill.claim.submit"])
    start_progress(peer.membership, course, peer.person)

    gap = learner.client().get(URL, {"target": str(profile.id)}).json()["gaps"][0]

    assert gap["resources"][0]["progress"] is None


def test_a_fully_met_profile_has_no_gaps(learner, acme, skills):
    profile = _profile(acme, [(skills["sql"], 2, "core")])
    _verify(learner, skills["sql"], 3)

    resp = learner.client().get(URL, {"target": str(profile.id)})

    assert resp.json() == {"job_profile": str(profile.id), "gaps": []}


@pytest.mark.parametrize("query", [{}, {"target": "not-a-uuid"}], ids=["missing", "malformed"])
def test_target_must_be_a_profile_id(learner, query):
    assert learner.client().get(URL, query).status_code == 400


def test_another_tenants_profile_is_not_found(learner, globex, skills):
    foreign = _profile(globex, [(skills["sql"], 2, "core")])

    assert learner.client().get(URL, {"target": str(foreign.id)}).status_code == 404


def test_another_tenants_resources_are_never_recommended(learner, acme, globex, skills):
    profile = _profile(acme, [(skills["sql"], 2, "core")])
    make_resource(globex, "Globex SQL", [(skills["sql"], 2)])

    gap = learner.client().get(URL, {"target": str(profile.id)}).json()["gaps"][0]

    assert gap["resources"] == []


def test_member_without_skill_claim_submit_is_forbidden(acme, skills):
    profile = _profile(acme, [(skills["sql"], 2, "core")])
    viewer = make_member(acme, "viewer@acme.test", ["directory.view"])

    assert viewer.client().get(URL, {"target": str(profile.id)}).status_code == 403
