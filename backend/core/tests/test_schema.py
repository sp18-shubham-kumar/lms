import pytest
from rest_framework.test import APIClient


@pytest.mark.django_db
def test_schema_is_200_and_includes_part_a_paths():
    client = APIClient()
    resp = client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]

    expected = [
        "/api/skills/",
        "/api/skills/me/declarations/",
        "/api/authz/grants/",
        "/api/authz/roles/",
        "/api/identity/members/import/",
        "/api/identity/people/",
    ]
    for path in expected:
        assert path in paths, f"{path} missing from schema"

    # Every Part A operation carries a summary and a tag.
    for path in expected:
        for method, operation in paths[path].items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert operation.get("summary"), f"{method} {path} missing summary"
            assert operation.get("tags"), f"{method} {path} missing tag"


@pytest.mark.django_db
def test_schema_includes_part_b_paths():
    """
    Every Part B endpoint must appear in the OpenAPI schema with a summary and tag.
    Paths checked: profiles/me/readiness/, profiles/heatmap/, skills/assertions/,
    and skills/{id}/levels/.
    """
    client = APIClient()
    resp = client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json")
    assert resp.status_code == 200
    schema = resp.json()
    paths = schema["paths"]

    expected_part_b = [
        "/api/profiles/me/readiness/",
        "/api/profiles/heatmap/",
        "/api/skills/assertions/",
        "/api/skills/{id}/levels/",
    ]
    for path in expected_part_b:
        assert path in paths, f"Part B path {path} missing from schema"

    # Every operation on these paths must carry a summary and a tag.
    for path in expected_part_b:
        for method, operation in paths[path].items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            assert operation.get("summary"), f"{method} {path} missing summary in schema"
            assert operation.get("tags"), f"{method} {path} missing tag in schema"
