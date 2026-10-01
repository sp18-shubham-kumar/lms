import pytest
from django.contrib.auth import get_user_model

from core.context import tenant_context
from core.permissions import can

Person = get_user_model()


def _seed(cap_key):
    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    person = Person.objects.create_user(email="a@acme.test", display_name="A")
    cap = Capability.objects.create(key=cap_key)
    with tenant_context(tenant.id):
        Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
    return tenant, person


@pytest.mark.django_db
def test_can_grants_held_capability():
    tenant, person = _seed("directory.view")
    with tenant_context(tenant.id):
        assert can(person, "directory.view") is True


@pytest.mark.django_db
def test_can_denies_unheld_capability():
    tenant, person = _seed("directory.view")
    with tenant_context(tenant.id):
        assert can(person, "skill.verify") is False


@pytest.mark.django_db
def test_can_denies_without_tenant_context():
    _tenant, person = _seed("directory.view")
    # No tenant_context: must not raise, must return False.
    assert can(person, "directory.view") is False
