# backend/core/tests/test_tenant_membership_permission.py
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate

from core.context import tenant_context
from core.permissions import IsActiveTenantMember

Person = get_user_model()


@pytest.mark.django_db
def test_member_of_active_tenant_is_allowed():
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A")
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
    request = APIRequestFactory().get("/api/auth/session/")
    force_authenticate(request, user=person)
    request.user = person
    with tenant_context(tenant.id):
        assert IsActiveTenantMember().has_permission(request, view=None) is True


@pytest.mark.django_db
def test_non_member_is_denied():
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="stranger@x.test", display_name="S")
    request = APIRequestFactory().get("/api/auth/session/")
    request.user = person
    with tenant_context(tenant.id):
        assert IsActiveTenantMember().has_permission(request, view=None) is False


def test_unauthenticated_is_denied():
    request = APIRequestFactory().get("/api/auth/session/")
    request.user = AnonymousUser()
    assert IsActiveTenantMember().has_permission(request, view=None) is False


@pytest.mark.django_db
def test_no_tenant_context_raises_validation_error():
    person = Person.objects.create_user(email="notenant@x.test", display_name="NT")
    request = APIRequestFactory().get("/api/auth/session/")
    request.user = person
    with pytest.raises(ValidationError) as exc:
        IsActiveTenantMember().has_permission(request, view=None)
    assert "tenant" in exc.value.detail
