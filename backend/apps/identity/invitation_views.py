"""Member invitation endpoints. Accept stays on the public auth route."""

from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.identity.invitation_service import (
    InvitationError,
    cancel_invitation,
    create_invitation,
    resend_invitation,
    resolve_role,
)
from apps.identity.models import Invitation
from apps.identity.serializers import (
    InvitationCreateSerializer,
    InvitationPayloadSerializer,
    InvitationSerializer,
)
from core.context import get_current_tenant
from core.permissions import HasCapability


class InvitationListView(ListAPIView):
    """Pending invitations in the active tenant. Gated by member.invite."""

    serializer_class = InvitationSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "member.invite"

    @extend_schema(
        summary="List pending invitations",
        description="Pending email invitations for the active tenant. Gated by member.invite.",
        tags=["Identity"],
    )
    def get(self, request: Any, *args: Any, **kwargs: Any) -> Response:
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> Any:
        return (
            Invitation.objects.filter(status=Invitation.Status.PENDING)
            .select_related("role")
            .order_by("-created_at")
        )

    @extend_schema(
        summary="Invite a member by email",
        description=(
            "Creates a pending invitation for ``email`` and the role name or id. "
            "Emails the same accept link used everywhere else. The raw token is "
            "returned once; only its hash is stored. Gated by member.invite."
        ),
        tags=["Identity"],
        request=InvitationCreateSerializer,
        responses={201: InvitationPayloadSerializer},
    )
    def post(self, request: Any) -> Response:
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tenant_id = get_current_tenant()
        try:
            role = resolve_role(role_ref=serializer.validated_data["role"], tenant_id=tenant_id)
            payload = create_invitation(
                email=serializer.validated_data["email"],
                role_name=role.name,
                role=role,
                actor=request.user,
                tenant_id=tenant_id,
            )
        except InvitationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        return Response(payload, status=status.HTTP_201_CREATED)


class InvitationResendView(APIView):
    """Issue a new token for a pending invitation. Gated by member.invite."""

    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "member.invite"

    @extend_schema(
        summary="Resend an invitation",
        description=(
            "Replaces the token and expiry of a pending invitation and emails the "
            "new link. The previous token stops working. Gated by member.invite."
        ),
        tags=["Identity"],
        request=None,
        responses=InvitationPayloadSerializer,
    )
    def post(self, request: Any, id: Any) -> Response:
        try:
            payload = resend_invitation(
                invitation_id=id, actor=request.user, tenant_id=get_current_tenant()
            )
        except InvitationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        return Response(payload)


class InvitationCancelView(APIView):
    """Cancel a pending invitation so the email can be invited again."""

    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "member.invite"

    @extend_schema(
        summary="Cancel an invitation",
        description=(
            "Marks a pending invitation cancelled. That email can be invited again. "
            "Gated by member.invite."
        ),
        tags=["Identity"],
        responses={204: None},
    )
    def delete(self, request: Any, id: Any) -> Response:
        try:
            cancel_invitation(invitation_id=id, actor=request.user, tenant_id=get_current_tenant())
        except InvitationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        return Response(status=status.HTTP_204_NO_CONTENT)
