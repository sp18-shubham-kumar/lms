from __future__ import annotations

from typing import Any

from django.db import transaction
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
from apps.authz.serializers import (
    CapabilitySerializer,
    RoleGrantSerializer,
    RoleSerializer,
    RoleWriteSerializer,
)
from core import audit
from core.context import get_current_tenant
from core.idempotency import IdempotentCreateMixin
from core.permissions import HasCapability

INVITE_CAPABILITY = "member.invite"
OFFBOARD_CAPABILITY = "member.offboard"


def _replace_capabilities(role: Role, keys: list[str], tenant_id: Any) -> None:
    """Replace a role's capability set. Unknown keys are rejected before any write."""
    unique = list(dict.fromkeys(keys))
    known = set(Capability.objects.filter(key__in=unique).values_list("key", flat=True))
    missing = [key for key in unique if key not in known]
    if missing:
        raise ValidationError({"capabilities": [f"Unknown capability: {key}" for key in missing]})
    current = RoleCapability.objects.filter(role=role)
    if not unique:
        current.delete()
        return
    current.exclude(capability_id__in=unique).delete()
    have = set(current.values_list("capability_id", flat=True))
    for key in unique:
        if key not in have:
            RoleCapability.objects.create(tenant_id=tenant_id, role=role, capability_id=key)


@extend_schema_view(
    list=extend_schema(
        summary="List roles and their capabilities",
        description="Roles defined in the active tenant with their granted capability keys.",
        tags=["Authz"],
    ),
    retrieve=extend_schema(summary="Retrieve a role", tags=["Authz"]),
    create=extend_schema(
        summary="Create a role",
        description=(
            "Create a role in the active tenant and attach existing capability keys. "
            "Gated by member.invite."
        ),
        tags=["Authz"],
        request=RoleWriteSerializer,
        responses=RoleSerializer,
    ),
    partial_update=extend_schema(
        summary="Update a role",
        description="Update the name and/or replace the capability keys. Gated by member.invite.",
        tags=["Authz"],
        request=RoleWriteSerializer,
        responses=RoleSerializer,
    ),
    destroy=extend_schema(
        summary="Delete a role with no grants",
        description="Deletes the role only when no role grant still uses it. Gated by member.invite.",
        tags=["Authz"],
    ),
)
class RoleViewSet(
    IdempotentCreateMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    """Tenant roles and their capability keys. Writes are gated by member.invite."""

    serializer_class = RoleSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = INVITE_CAPABILITY
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self) -> Any:
        # Role.objects is tenant-scoped (fails closed with no tenant in context).
        return Role.objects.prefetch_related("capabilities").order_by("name")

    def get_serializer_class(self) -> type[RoleSerializer] | type[RoleWriteSerializer]:
        if self.action in {"create", "partial_update"}:
            return RoleWriteSerializer
        return RoleSerializer

    @transaction.atomic
    def _create_role(self, request: Any) -> Response:
        serializer = RoleWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_id = get_current_tenant()
        name = serializer.validated_data["name"]
        if Role.objects.filter(name=name).exists():
            raise ValidationError({"name": "A role with this name already exists."})
        role = Role.objects.create(tenant_id=tenant_id, name=name, is_system=False)
        _replace_capabilities(role, serializer.validated_data["capabilities"], tenant_id)
        audit.record(
            actor=request.user,
            action="role.create",
            resource=role,
            tenant_id=tenant_id,
            name=name,
        )
        return Response(RoleSerializer(role).data, status=201)

    def create(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return self.idempotent_create(request, lambda: self._create_role(request))

    @transaction.atomic
    def partial_update(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        role = self.get_object()
        serializer = RoleWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        tenant_id = get_current_tenant()
        data = serializer.validated_data
        if "name" in data and data["name"] != role.name:
            if Role.objects.filter(name=data["name"]).exclude(id=role.id).exists():
                raise ValidationError({"name": "A role with this name already exists."})
            role.name = data["name"]
            role.save(update_fields=["name", "updated_at"])
        if "capabilities" in data:
            _replace_capabilities(role, data["capabilities"], tenant_id)
        audit.record(
            actor=request.user,
            action="role.update",
            resource=role,
            tenant_id=tenant_id,
            name=role.name,
        )
        return Response(RoleSerializer(role).data)

    def destroy(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        role = self.get_object()
        if role.grants.exists():
            raise ValidationError("This role is still granted and cannot be deleted.")
        audit.record(
            actor=request.user,
            action="role.delete",
            resource=role,
            tenant_id=role.tenant_id,
            name=role.name,
        )
        role.delete()
        return Response(status=204)


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
        qs = RoleGrant.objects.select_related("role").order_by("-created_at")
        principal_id = self.request.query_params.get("principal_id")
        if principal_id:
            qs = qs.filter(principal_type="person", principal_id=principal_id)
        return qs

    @extend_schema(
        summary="List role grants",
        tags=["Authz"],
        parameters=[
            OpenApiParameter(
                "principal_id",
                OpenApiTypes.UUID,
                description="Only grants held by this person.",
            )
        ],
    )
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
        # Force principal_type to "person" — group grants are not resolved by
        # capabilities_for() yet and would silently never take effect.
        grant = serializer.save(tenant_id=tenant_id, principal_type="person")
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


@extend_schema(
    summary="List capability keys",
    description=(
        "Every capability key a role can bundle. The list is global and seeded; it is "
        "what the role editor offers as checkboxes. Gated by member.invite."
    ),
    tags=["Authz"],
    responses=CapabilitySerializer(many=True),
)
class CapabilityListView(APIView):
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = INVITE_CAPABILITY

    def get(self, request: Any) -> Response:
        keys = Capability.objects.order_by("key")
        return Response(CapabilitySerializer(keys, many=True).data)
