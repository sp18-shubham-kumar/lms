import pytest

from core import audit
from core.models import AuditLog


@pytest.mark.django_db
def test_record_inserts_audit_row():
    audit.record(actor=None, action="auth.login", tenant_id=None, email="x@y.z")
    row = AuditLog.objects.get()
    assert row.action == "auth.login"
    assert row.metadata == {"email": "x@y.z"}
