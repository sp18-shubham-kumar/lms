"""Platform-operator endpoints. These are not tenant-scoped."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.invitation_service import InvitationError
from apps.identity.provision import ProvisionError, provision_tenant
from apps.identity.serializers import (
    TenantProvisionResponseSerializer,
    TenantProvisionSerializer,
)


class IsPlatformOperator(BasePermission):
    """Django staff superuser. Tenant membership is not required."""

    message = "Platform operator access is required."

    def has_permission(self, request: Any, view: Any) -> bool:
        user = getattr(request, "user", None)
        return bool(
            user is not None and user.is_authenticated and user.is_staff and user.is_superuser
        )


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
class TenantProvisionView(APIView):
    permission_classes = [IsAuthenticated, IsPlatformOperator]
    authentication_classes = APIView.authentication_classes

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
