"""
OpenAPI schema customisation (drf-spectacular).

Tenant-scoped endpoints need two credentials: the JWT *and* the ``X-Tenant-Id``
header. Rather than repeating a header parameter on every operation, the tenant
header is modelled as a security scheme and attached to every operation whose
view enforces :class:`core.permissions.IsActiveTenantMember`. Swagger UI then
asks for both once, under "Authorize", and sends them on every "Try it out".

Public endpoints (login, invitation accept, health) and platform-operator
endpoints don't enforce tenant membership, so they don't get the tenant scheme.
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.openapi import AutoSchema

from core.permissions import IsActiveTenantMember

# Declared under SPECTACULAR_SETTINGS["APPEND_COMPONENTS"] in config/settings/base.py.
TENANT_SECURITY_SCHEME = "tenantHeader"


class TenantAwareAutoSchema(AutoSchema):
    """AutoSchema that requires the tenant header wherever tenant membership is enforced."""

    def _requires_tenant(self) -> bool:
        return any(isinstance(perm, IsActiveTenantMember) for perm in self.view.get_permissions())

    def get_auth(self) -> list[dict[str, Any]]:
        auth = super().get_auth()
        if not self._requires_tenant():
            return auth
        # OpenAPI ANDs the schemes inside one requirement object: JWT *and* tenant header.
        return [{**requirement, TENANT_SECURITY_SCHEME: []} for requirement in auth if requirement]
