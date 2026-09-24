"""Smoke tests that prove the project boots and core seams work."""

from __future__ import annotations

from uuid import uuid4

import pytest
from django.urls import reverse

from core.context import get_current_tenant, tenant_context


@pytest.mark.django_db
def test_health_endpoint_ok(client):
    """/api/health/ returns 200 and reports DB connectivity."""
    resp = client.get(reverse("health"))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_tenant_context_roundtrip():
    """The ambient tenant context sets and clears cleanly."""
    assert get_current_tenant() is None
    tid = uuid4()
    with tenant_context(tid):
        assert get_current_tenant() == tid
    assert get_current_tenant() is None
