"""Platform-operator endpoints. These are not tenant-scoped."""

from __future__ import annotations

from typing import Any

from django.db.models import Count, OuterRef, Subquery
from django.db.models.functions import Coalesce
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.invitation_service import InvitationError
from apps.identity.models import Membership, Tenant
from apps.identity.provision import ProvisionError, provision_tenant
from apps.identity.serializers import (
    PlatformTenantSerializer,
    TenantProvisionResponseSerializer,
    TenantProvisionSerializer,
)


def is_platform_operator(user: Any) -> bool:
    """Django staff superuser. The one definition used by login, account and platform views."""
    return bool(user is not None and user.is_authenticated and user.is_staff and user.is_superuser)


class IsPlatformOperator(BasePermission):
    """Platform operator. Tenant membership is not required."""

    message = "Platform operator access is required."

    def has_permission(self, request: Any, view: Any) -> bool:
        return is_platform_operator(getattr(request, "user", None))


class TenantProvisionView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformOperator]
    authentication_classes = APIView.authentication_classes

    @extend_schema(
        summary="List tenants",
        description=(
            "Platform operators only. Every tenant with its count of active members, "
            "newest first. Do not send X-Tenant-Id."
        ),
        tags=["Platform"],
        responses=PlatformTenantSerializer(many=True),
    )
    def get(self, request: Any) -> Response:
        # Membership.tenant has no reverse accessor (related_name="+"), so count via
        # a correlated subquery over the unscoped manager.
        active_members = (
            Membership.all_tenants.filter(tenant=OuterRef("pk"), status="active")
            .values("tenant")
            .annotate(n=Count("id"))
            .values("n")
        )
        tenants = Tenant.objects.annotate(
            member_count=Coalesce(Subquery(active_members), 0)
        ).order_by("-created_at")
        return Response(PlatformTenantSerializer(tenants, many=True).data)

    @extend_schema(
        summary="Create a tenant and its first admin",
        description=(
            "Platform operators only (Django staff and superuser). Creates the organisation, "
            "the Tenant Admin role (including member.invite), a person with an unusable "
            "password, and a pending invitation. Emails the same accept link a member "
            "invite uses. Do not send X-Tenant-Id. The admin joins through "
            "POST /api/auth/invitations/accept/."
        ),
        tags=["Platform"],
        request=TenantProvisionSerializer,
        responses={201: TenantProvisionResponseSerializer},
    )
    def post(self, request: Any) -> Response:
        serializer = TenantProvisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        try:
            payload = provision_tenant(
                name=data["name"],
                slug=data["slug"],
                admin_email=data["admin_email"],
                actor=request.user,
            )
        except ProvisionError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        except InvitationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        return Response(payload, status=status.HTTP_201_CREATED)
