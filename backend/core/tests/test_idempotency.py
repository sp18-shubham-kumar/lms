"""
Idempotency-Key handling for write endpoints.

A client that retries a POST with the same ``Idempotency-Key`` must get the
first call's status/body back and must not create a duplicate row. Requests
without the header run normally and store nothing.
"""

from __future__ import annotations

import uuid

import pytest
from rest_framework import serializers, viewsets
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from core.context import tenant_context
from core.idempotency import IdempotentCreateMixin, idempotent


class _Payload(serializers.Serializer):
    value = serializers.CharField()

    def create(self, validated_data: dict) -> dict:
        return validated_data


class _ToyViewSet(IdempotentCreateMixin, viewsets.ViewSet):
    # Count real creates so the test can assert "exactly one row".
    created: list[str] = []
    authentication_classes: list = []
    permission_classes: list = []

    def perform_real_create(self, request):
        serializer = _Payload(data=request.data)
        serializer.is_valid(raise_exception=True)
        value = serializer.validated_data["value"]
        _ToyViewSet.created.append(value)
        return Response({"value": value, "n": len(_ToyViewSet.created)}, status=201)

    def create(self, request, *args, **kwargs):
        return self.idempotent_create(request, lambda: self.perform_real_create(request))


@pytest.fixture
def tenant_db():
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    return tenant


@pytest.mark.django_db
def test_replay_returns_first_result_and_creates_one_row(tenant_db) -> None:
    from core.models import IdempotencyRecord

    _ToyViewSet.created = []
    tenant = tenant_db
    view = _ToyViewSet.as_view({"post": "create"})

    def call():
        request = APIRequestFactory().post(
            "/toy/", {"value": "hello"}, format="json", HTTP_IDEMPOTENCY_KEY="k1"
        )
        force_authenticate(request, user=None)
        request.tenant_id = tenant.id
        with tenant_context(tenant.id):
            return view(request)

    first = call()
    second = call()

    assert first.status_code == 201
    assert second.status_code == first.status_code
    assert second.data == first.data
    assert len(_ToyViewSet.created) == 1
    with tenant_context(tenant.id):
        assert IdempotencyRecord.objects.filter(key="k1").count() == 1


@pytest.mark.django_db
def test_no_key_runs_normally_and_stores_nothing(tenant_db) -> None:
    from core.models import IdempotencyRecord

    _ToyViewSet.created = []
    tenant = tenant_db
    view = _ToyViewSet.as_view({"post": "create"})

    def call():
        request = APIRequestFactory().post("/toy/", {"value": "x"}, format="json")
        force_authenticate(request, user=None)
        request.tenant_id = tenant.id
        with tenant_context(tenant.id):
            return view(request)

    call()
    call()

    assert len(_ToyViewSet.created) == 2
    with tenant_context(tenant.id):
        assert IdempotencyRecord.objects.count() == 0


@pytest.mark.django_db
def test_idempotent_helper_persists_and_replays(tenant_db) -> None:
    from core.models import IdempotencyRecord

    tenant = tenant_db
    calls = {"n": 0}

    def factory():
        calls["n"] += 1
        return Response({"id": str(uuid.uuid4()), "n": calls["n"]}, status=201)

    request = APIRequestFactory().post("/thing/", HTTP_IDEMPOTENCY_KEY="abc")

    with tenant_context(tenant.id):
        r1 = idempotent(request, tenant.id, factory)
        r2 = idempotent(request, tenant.id, factory)

    assert calls["n"] == 1
    assert r1.status_code == r2.status_code == 201
    assert r2.data == r1.data
    with tenant_context(tenant.id):
        assert IdempotencyRecord.objects.filter(key="abc").count() == 1
