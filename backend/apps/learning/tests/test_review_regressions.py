"""
Regressions from the backend review: malformed query parameters answer 400, a
resource update audits the links it was saved with, and recommendations don't
issue a query per progress row.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.learning.tests.conftest import make_resource
from apps.learning.tests.test_recommendations import _profile

pytestmark = pytest.mark.django_db

RESOURCES_URL = "/api/learning/resources/"
RECOMMENDATIONS_URL = "/api/learning/me/recommendations/"


@pytest.mark.parametrize(
    ("url", "param"),
    [
        (RESOURCES_URL, "skill"),
        (RECOMMENDATIONS_URL, "target"),
        ("/api/profiles/me/readiness/", "target"),
    ],
)
def test_malformed_uuid_query_param_is_a_400(learner, url, param):
    resp = learner.client().get(url, {param: "not-a-uuid"})

    assert resp.status_code == 400, resp.content
    assert f"Query parameter '{param}' must be a UUID." in str(resp.json())


def test_resource_update_audits_the_new_skill_links(editor, acme, skills):
    from core.models import AuditLog

    resource = make_resource(acme, "Python basics", [(skills["python"], 1)])

    resp = editor.client().patch(
        f"{RESOURCES_URL}{resource.id}/",
        {"skills": [{"skill": str(skills["sql"].id), "level": 2}]},
        format="json",
    )

    assert resp.status_code == 200, resp.json()
    assert [link["skill"] for link in resp.json()["skills"]] == [str(skills["sql"].id)]
    entry = AuditLog.objects.filter(action="resource.update", resource_id=resource.id).get()
    assert entry.metadata["skill_ids"] == [str(skills["sql"].id)]


def _recommendation_queries(learner, acme, profile, skill, count, offset):
    from apps.learning.models import LearningProgress
    from core.context import tenant_context

    for i in range(count):
        resource = make_resource(acme, f"SQL {offset + i}", [(skill, 2)])
        with tenant_context(acme.id):
            LearningProgress.objects.create(
                tenant=acme,
                membership=learner.membership,
                resource=resource,
                status="in_progress",
            )
    client = learner.client()
    with CaptureQueriesContext(connection) as ctx:
        resp = client.get(RECOMMENDATIONS_URL, {"target": str(profile.id)})
    assert resp.status_code == 200, resp.json()
    return len(ctx.captured_queries), resp.json()


def test_recommendation_query_count_does_not_grow_with_progress_rows(learner, acme, skills):
    profile = _profile(acme, [(skills["sql"], 3, "core")])

    one, _ = _recommendation_queries(learner, acme, profile, skills["sql"], 1, 0)
    many, body = _recommendation_queries(learner, acme, profile, skills["sql"], 4, 1)

    assert len(body["gaps"][0]["resources"]) == 5
    assert all(row["progress"] is not None for row in body["gaps"][0]["resources"])
    assert many == one
