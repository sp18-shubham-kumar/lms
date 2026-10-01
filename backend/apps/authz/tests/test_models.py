import pytest

from core.context import tenant_context


@pytest.mark.django_db
def test_role_capabilities_link():
    from apps.authz.models import Capability, Role, RoleCapability
    from apps.identity.models import Tenant

    tenant = Tenant.objects.create(slug="acme", name="Acme", status="active", plan="pro")
    cap = Capability.objects.create(key="directory.view")
    with tenant_context(tenant.id):
        role = Role.objects.create(tenant=tenant, name="Learner", is_system=True)
        RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
        keys = list(role.capabilities.values_list("capability_id", flat=True))
    assert keys == ["directory.view"]
