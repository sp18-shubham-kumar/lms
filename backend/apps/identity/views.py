from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import BaseParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity import import_service, invitation_service
from apps.identity.invitation_service import InvitationError
from apps.identity.models import Invitation, Membership, OrgUnit, Tenant
from apps.identity.serializers import (
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    LoginSerializer,
    MembershipSummarySerializer,
    PersonDirectorySerializer,
    PersonSummarySerializer,
    TenantSummarySerializer,
)
from apps.skills.models import SelfDeclaredSkill
from core import audit
from core.context import get_current_tenant
from core.idempotency import idempotent
from core.pagination import DefaultPagination
from core.permissions import HasCapability, capabilities_for


class CSVParser(BaseParser):
    """Passthrough parser for ``text/csv`` so DRF accepts a raw CSV request body."""

    media_type = "text/csv"

    def parse(  # type: ignore[override]  # returns raw text, not a parsed mapping
        self, stream: Any, media_type: Any = None, parser_context: Any = None
    ) -> str:
        return stream.read().decode("utf-8")


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


@extend_schema(
    summary="List directory members",
    description=(
        "Paginated directory of the active tenant's ACTIVE members. "
        "Optional filters: ``skill`` (members who declared it), ``level`` "
        "(minimum declared level, use with ``skill``), ``org_unit`` (subtree)."
    ),
    tags=["Identity"],
    parameters=[
        OpenApiParameter(
            "skill", OpenApiTypes.UUID, description="Filter to members who declared this skill."
        ),
        OpenApiParameter(
            "level",
            OpenApiTypes.INT,
            description="Minimum declared level (requires ``skill``).",
        ),
        OpenApiParameter(
            "org_unit",
            OpenApiTypes.UUID,
            description="Filter to members in this org unit's subtree.",
        ),
    ],
)
class PeopleListView(ListAPIView):
    """Paginated directory of the active tenant's ACTIVE members. Gated by directory.view.

    Only memberships with status="active" are included; ended or suspended memberships
    are hidden per spec (data-model.md: "Ending a membership hides the person from
    tenant reports").

    Supports filters ``?skill=&org_unit=&level=``:

    - ``skill`` (and optional minimum ``level``): members who hold the skill. Phase 1
      reads the self-declared tier (``SelfDeclaredSkill``). **Part B switch:** once the
      verified ``SkillAssertion`` tier lands, filter on that instead (the directory
      should surface verified capability, not self-claims).
    - ``org_unit``: members whose org unit is in the given unit's subtree, matched by
      the materialised ``path`` prefix (``path == target`` or ``path startswith
      target + "."``). All queries stay tenant-scoped via ``Membership.objects``.
    """

    serializer_class = PersonDirectorySerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "directory.view"

    def get_queryset(self):
        # Membership.objects is tenant-scoped (fails closed with no tenant in context).
        qs = (
            Membership.objects.filter(status="active")
            .select_related("person", "org_unit")
            .order_by("person__display_name")
        )
        params = self.request.query_params

        skill_id = params.get("skill")
        if skill_id:
            # Phase 1: self-declared tier. Part B: switch to verified SkillAssertion.
            declared = SelfDeclaredSkill.objects.filter(skill_id=skill_id)
            level = params.get("level")
            if level:
                declared = declared.filter(level__gte=level)
            qs = qs.filter(id__in=declared.values("membership_id"))

        org_unit_id = params.get("org_unit")
        if org_unit_id:
            target = OrgUnit.objects.filter(id=org_unit_id).first()
            if target is None:
                return qs.none()
            # Subtree via materialised path prefix: the unit itself + descendants.
            qs = qs.filter(
                Q(org_unit__path=target.path) | Q(org_unit__path__startswith=f"{target.path}.")
            )

        return qs


def _read_csv_body(request: Any) -> str:
    """Extract the CSV text from a raw body, an uploaded file, or a JSON {"csv": ...}."""
    upload = request.FILES.get("file")
    if upload is not None:
        return upload.read().decode("utf-8")
    data = request.data
    if isinstance(data, str):  # CSVParser returned the raw body as a string
        return data
    if isinstance(data, dict) and "csv" in data:
        return str(data["csv"])
    body = request.body
    return body.decode("utf-8") if isinstance(body, bytes) else str(body)


@extend_schema(
    summary="Import members from CSV",
    description=(
        "Upload a CSV (columns ``email,display_name,org_unit_path,role,employee_ref``). "
        "Returns a dry-run diff ``{adds, updates, errors}`` without writing. "
        "Pass ``?commit=true`` to apply the diff (create persons/memberships, attach "
        "roles) — audited, and idempotent via the ``Idempotency-Key`` header."
    ),
    tags=["Identity"],
    parameters=[
        OpenApiParameter(
            "commit", OpenApiTypes.BOOL, description="Apply the diff instead of a dry run."
        ),
    ],
    request=OpenApiTypes.BINARY,
    responses=OpenApiTypes.OBJECT,
)
class MemberImportView(APIView):
    """CSV member import: dry-run diff, or ``?commit=true`` to apply. Gated by member.invite."""

    permission_classes = [*APIView.permission_classes, HasCapability]
    parser_classes = [*APIView.parser_classes, CSVParser]
    required_capability = "member.invite"

    def post(self, request: Any) -> Response:
        tenant_id = get_current_tenant()
        raw = _read_csv_body(request)
        diff = import_service.build_diff(raw, tenant_id)

        commit = request.query_params.get("commit", "").lower() in {"true", "1", "yes"}
        if not commit:
            return Response(diff.as_dict())

        def _apply() -> Response:
            result = import_service.apply_diff(diff, tenant_id, request.user)
            return Response(result)

        # Commit is idempotent: a retry with the same Idempotency-Key replays the result.
        return idempotent(request, tenant_id, _apply)


def _invitation_error(exc: InvitationError) -> Response:
    return Response({"detail": exc.detail}, status=exc.status_code)


class InvitationListCreateView(APIView):
    """List and create pending email invitations. Gated by member.invite."""

    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "member.invite"
    pagination_class = DefaultPagination

    @extend_schema(
        summary="List pending invitations",
        description="Pending email invitations for the active tenant.",
        tags=["Identity"],
    )
    def get(self, request: Any) -> Response:
        queryset = (
            Invitation.objects.filter(status=Invitation.Status.PENDING)
            .select_related("role")
            .order_by("-created_at")
        )
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(queryset, request, view=self)
        rows = page if page is not None else queryset
        data = [invitation_service.to_payload(row) for row in rows]
        if page is not None:
            return paginator.get_paginated_response(data)
        return Response(data)

    @extend_schema(
        summary="Invite a member by email",
        description=(
            "Create a pending invitation and email a one-time accept link. "
            "Only the token hash is stored. Requires member.invite."
        ),
        tags=["Identity"],
        request=InvitationCreateSerializer,
    )
    def post(self, request: Any) -> Response:
        serializer = InvitationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = invitation_service.create_invitation(
                email=serializer.validated_data["email"],
                role_name=serializer.validated_data["role"],
                actor=request.user,
                tenant_id=get_current_tenant(),
            )
        except InvitationError as exc:
            return _invitation_error(exc)
        return Response(payload, status=status.HTTP_201_CREATED)


@extend_schema(
    summary="Accept an email invitation",
    description=(
        "Public. Set a password from the emailed token, creating the person and "
        "membership when needed. The token is single-use."
    ),
    tags=["Auth"],
    request=InvitationAcceptSerializer,
)
class InvitationAcceptView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list[Any] = []

    def post(self, request: Any) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = invitation_service.accept_invitation(
                raw_token=serializer.validated_data["token"],
                password=serializer.validated_data["password"],
            )
        except InvitationError as exc:
            return _invitation_error(exc)
        return Response(payload)
