from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authz.models import Role, RoleGrant
from apps.authz.serializers import RoleGrantSerializer, RoleSerializer
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

INVITE_CAPABILITY = "member.invite"
OFFBOARD_CAPABILITY = "member.offboard"


@extend_schema(
    summary="List roles and their capabilities",
    description="Roles defined in the active tenant with their granted capability keys.",
    tags=["Authz"],
)
class RoleViewSet(viewsets.ReadOnlyModelViewSet):
    """Read-only list of the tenant's roles + capability keys. Gated by member.invite."""

    serializer_class = RoleSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = INVITE_CAPABILITY

    def get_queryset(self) -> Any:
        # Role.objects is tenant-scoped (fails closed with no tenant in context).
        return Role.objects.prefetch_related("capabilities").order_by("name")


@extend_schema(tags=["Authz"])
class RoleGrantViewSet(
    IdempotentCreateMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """
    Manage role grants in the active tenant.

    POST (``member.invite``) grants a role to a principal; DELETE
    (``member.offboard``) revokes it. Reads are tenant-scoped and isolation-tested.
    Both writes are audited. Create is idempotent via the ``Idempotency-Key`` header.

    Capability caching: ``can()`` memoises capabilities per request on the actor
    (no persistent cache to invalidate), so a grant write takes effect on the next
    request automatically. If a persistent cache is added later, invalidate the
    affected principal here after create/destroy.
    """

    serializer_class = RoleGrantSerializer

    def get_permissions(self) -> list[Any]:
        capability = OFFBOARD_CAPABILITY if self.action == "destroy" else INVITE_CAPABILITY
        self.required_capability = capability
        perms: list[Any] = [perm() for perm in APIView.permission_classes]
        perms.append(HasCapability())
        return perms

    def get_queryset(self) -> Any:
        # RoleGrant.objects is tenant-scoped (fails closed with no tenant in context).
        return RoleGrant.objects.select_related("role").order_by("-created_at")

    @extend_schema(summary="List role grants", tags=["Authz"])
    def list(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return super().list(request, *args, **kwargs)

    @extend_schema(summary="Grant a role to a principal", tags=["Authz"])
    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(
            request, lambda: super(RoleGrantViewSet, self).create(request)
        )

    @extend_schema(summary="Revoke a role grant", tags=["Authz"])
    def destroy(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return super().destroy(request, *args, **kwargs)

    def perform_create(self, serializer: Any) -> None:
        tenant_id = get_current_tenant()
        grant = serializer.save(tenant_id=tenant_id)
        audit.record(
            actor=self.request.user,
            action="member.grant",
            resource=grant,
            tenant_id=tenant_id,
            principal_id=str(grant.principal_id),
            role_id=str(grant.role_id),
        )

    def perform_destroy(self, instance: RoleGrant) -> None:
        audit.record(
            actor=self.request.user,
            action="member.offboard",
            resource=instance,
            tenant_id=instance.tenant_id,
            principal_id=str(instance.principal_id),
            role_id=str(instance.role_id),
        )
        instance.delete()
