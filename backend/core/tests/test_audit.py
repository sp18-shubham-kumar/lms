import pytest
from django.contrib.auth import get_user_model

from core import audit
from core.models import AuditLog


@pytest.mark.django_db
def test_record_inserts_audit_row():
    audit.record(actor=None, action="auth.login", tenant_id=None, email="x@y.z")
    row = AuditLog.objects.get()
    assert row.action == "auth.login"
    assert row.metadata == {"email": "x@y.z"}


@pytest.mark.django_db
def test_record_stores_actor_id_when_actor_has_pk():
    Person = get_user_model()
    person = Person.objects.create_user(
        email="actor@example.com",
        display_name="Actor User",
        password="testpass123",
    )
    audit.record(actor=person, action="auth.login", tenant_id=None)
    row = AuditLog.objects.get()
    assert row.actor_id == person.id


@pytest.mark.django_db
def test_record_populates_resource_type_and_resource_id():
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
    audit.record(actor=None, action="tenant.create", resource=tenant, tenant_id=None)
    row = AuditLog.objects.get()
    assert row.resource_type == "Tenant"
    assert row.resource_id == tenant.id
