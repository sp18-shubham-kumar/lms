import os

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
        "/api/identity/invitations/",
        "/api/identity/invitations/{id}/",
        "/api/identity/invitations/{id}/resend/",
        "/api/identity/org-units/",
        "/api/auth/invitations/accept/",
        "/api/platform/tenants/",
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


def test_schema_generates_without_warnings():
    """Any undocumented view or untyped parameter fails the build, not just the docs."""
    from django.core.management import call_command

    call_command("spectacular", "--validate", "--fail-on-warn", "--file", os.devnull)


def _operation_security(schema: dict, method: str, path: str) -> set[str]:
    requirements = schema["paths"][path][method].get("security", [])
    return {name for requirement in requirements for name in requirement}


@pytest.mark.django_db
def test_tenant_header_is_required_only_where_membership_is_enforced():
    """Swagger's Authorize must offer X-Tenant-Id exactly where the API demands it."""
    client = APIClient()
    schema = client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json").json()

    assert schema["components"]["securitySchemes"]["tenantHeader"] == {
        "type": "apiKey",
        "in": "header",
        "name": "X-Tenant-Id",
        "description": schema["components"]["securitySchemes"]["tenantHeader"]["description"],
    }

    for method, path in [
        ("get", "/api/auth/session/"),
        ("get", "/api/identity/people/"),
        ("get", "/api/profiles/heatmap/"),
        ("post", "/api/skills/me/declarations/"),
    ]:
        assert _operation_security(schema, method, path) == {"jwtAuth", "tenantHeader"}, path

    for method, path in [
        ("post", "/api/auth/login/"),
        ("post", "/api/auth/invitations/accept/"),
        ("get", "/api/health/"),
    ]:
        assert "tenantHeader" not in _operation_security(schema, method, path), path

    # Platform operators provision tenants they don't belong to: JWT only.
    assert _operation_security(schema, "post", "/api/platform/tenants/") == {"jwtAuth"}


@pytest.mark.django_db
def test_login_documents_its_request_and_token_response():
    client = APIClient()
    schema = client.get("/api/schema/", HTTP_ACCEPT="application/vnd.oai.openapi+json").json()
    login = schema["paths"]["/api/auth/login/"]["post"]

    request_ref = login["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    response_ref = login["responses"]["200"]["content"]["application/json"]["schema"]["$ref"]
    components = schema["components"]["schemas"]
    assert set(components[request_ref.rsplit("/", 1)[-1]]["properties"]) == {"email", "password"}
    assert set(components[response_ref.rsplit("/", 1)[-1]]["properties"]) == {
        "access",
        "refresh",
        "memberships",
    }
