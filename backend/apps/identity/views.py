from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity.models import Membership, Tenant
from apps.identity.serializers import (
    LoginSerializer,
    MembershipSummarySerializer,
    PersonDirectorySerializer,
    PersonSummarySerializer,
    TenantSummarySerializer,
)
from core import audit
from core.context import get_current_tenant
from core.permissions import HasCapability, capabilities_for


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def get_authenticate_header(self, request: Any) -> str:
        # DRF coerces AuthenticationFailed → 403 when there is no WWW-Authenticate
        # header. Return a Bearer challenge so the 401 is preserved.
        return 'Bearer realm="api"'

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        person = authenticate(
            request,
            username=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if person is None:
            raise AuthenticationFailed("Invalid email or password.")
        memberships = list(
            Membership.all_tenants.filter(person=person, status="active").select_related("tenant")
        )
        if not memberships:
            raise PermissionDenied("You have no active membership in any organization.")
        refresh = RefreshToken.for_user(person)
        audit.record(actor=person, action="auth.login")
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
            }
        )


class SessionView(APIView):
    """Who am I, in this tenant. Default permissions require auth + membership."""

    def get(self, request):
        tenant_id = get_current_tenant()
        tenant = Tenant.objects.get(id=tenant_id)
        memberships = list(
            Membership.all_tenants.filter(person=request.user, status="active").select_related(
                "tenant"
            )
        )
        return Response(
            {
                "person": PersonSummarySerializer(request.user).data,
                "tenant": TenantSummarySerializer(tenant).data,
                "capabilities": sorted(capabilities_for(request.user, tenant_id)),
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
            }
        )


class PeopleListView(ListAPIView):
    """Paginated directory of all active-tenant members. Gated by directory.view."""

    serializer_class = PersonDirectorySerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "directory.view"

    def get_queryset(self):
        # Membership.objects is tenant-scoped (fails closed with no tenant in context).
        return Membership.objects.select_related("person", "org_unit").order_by(
            "person__display_name"
        )
