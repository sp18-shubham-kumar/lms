from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate
from django.db.models import Q
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.exceptions import AuthenticationFailed, PermissionDenied
from rest_framework.generics import ListAPIView
from rest_framework.parsers import BaseParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from apps.identity import import_service
from apps.identity.invitation_service import InvitationError, accept_invitation
from apps.identity.models import Membership, OrgUnit, Tenant
from apps.identity.platform_views import is_platform_operator
from apps.identity.serializers import (
    AccountSerializer,
    InvitationAcceptResponseSerializer,
    InvitationAcceptSerializer,
    LoginResponseSerializer,
    LoginSerializer,
    MembershipSummarySerializer,
    OrgUnitSerializer,
    PersonDirectorySerializer,
    PersonSummarySerializer,
    SessionSerializer,
    TenantSummarySerializer,
)
from apps.skills.models import SelfDeclaredSkill
from core import audit
from core.context import get_current_tenant
from core.idempotency import idempotent
from core.permissions import HasCapability, capabilities_for


class CSVParser(BaseParser):
    """Passthrough parser for ``text/csv`` so DRF accepts a raw CSV request body."""

    media_type = "text/csv"

    def parse(  # type: ignore[override]  # returns raw text, not a parsed mapping
        self, stream: Any, media_type: Any = None, parser_context: Any = None
    ) -> str:
        return stream.read().decode("utf-8")


@extend_schema(
    summary="Log in",
    description=(
        "Public. Exchanges email + password for a JWT pair and the person's active "
        "memberships. Send no X-Tenant-Id. Use `access` as the Bearer token and a "
        "membership's `tenant_id` as X-Tenant-Id on every later call."
    ),
    tags=["Identity"],
    request=LoginSerializer,
    responses=LoginResponseSerializer,
)
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
        memberships = _active_memberships(person)
        operator = is_platform_operator(person)
        # A platform operator provisions tenants and may have no membership yet.
        if not memberships and not operator:
            raise PermissionDenied("You have no active membership in any organization.")
        refresh = RefreshToken.for_user(person)
        audit.record(actor=person, action="auth.login")
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "person": PersonSummarySerializer(person).data,
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
                "is_platform_operator": operator,
            }
        )


def _active_memberships(person: Any) -> list[Membership]:
    return list(
        Membership.all_tenants.filter(person=person, status="active").select_related("tenant")
    )


@extend_schema(
    summary="Current account",
    description=(
        "The signed-in person without a tenant: their active memberships and whether "
        "they are a platform operator. Needs the JWT only; send no X-Tenant-Id. The SPA "
        "uses it to restore a session that has no tenant selected."
    ),
    tags=["Identity"],
    responses=AccountSerializer,
)
class AccountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Any) -> Response:
        return Response(
            {
                "person": PersonSummarySerializer(request.user).data,
                "memberships": MembershipSummarySerializer(
                    _active_memberships(request.user), many=True
                ).data,
                "is_platform_operator": is_platform_operator(request.user),
            }
        )


@extend_schema(
    summary="Accept an invitation",
    description=(
        "Public. Consumes a one-time invitation token, sets the person's password, "
        "and opens their membership and role grant. No JWT and no X-Tenant-Id."
    ),
    tags=["Identity"],
    request=InvitationAcceptSerializer,
    responses=InvitationAcceptResponseSerializer,
)
class InvitationAcceptView(APIView):
    """The join path for a pending invitation, including the first tenant admin."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request: Any) -> Response:
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            payload = accept_invitation(
                raw_token=serializer.validated_data["token"],
                password=serializer.validated_data["password"],
            )
        except InvitationError as exc:
            return Response({"detail": exc.detail}, status=exc.status_code)
        return Response(payload)


@extend_schema(
    summary="Current session",
    description=(
        "The caller's person, the active tenant, the capability keys they hold in it, "
        "and all their active memberships. The SPA gates navigation on `capabilities`."
    ),
    tags=["Identity"],
    responses=SessionSerializer,
)
class SessionView(APIView):
    """Who am I, in this tenant. Default permissions require auth + membership."""

    def get(self, request):
        tenant_id = get_current_tenant()
        tenant = Tenant.objects.get(id=tenant_id)
        memberships = _active_memberships(request.user)
        return Response(
            {
                "person": PersonSummarySerializer(request.user).data,
                "tenant": TenantSummarySerializer(tenant).data,
                "capabilities": sorted(capabilities_for(request.user, tenant_id)),
                "memberships": MembershipSummarySerializer(memberships, many=True).data,
                "is_platform_operator": is_platform_operator(request.user),
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


@extend_schema(
    summary="List org units",
    description=(
        "List the active tenant's org units (id, name, materialised path, parent). "
        "Lets the SPA build org-unit filters and scope the team heatmap. "
        "Gated by directory.view."
    ),
    tags=["Identity"],
)
class OrgUnitListView(ListAPIView):
    """Paginated list of the active tenant's org units. Gated by directory.view.

    Tenant-scoped via ``OrgUnit.objects`` (fails closed with no tenant in context).
    """

    serializer_class = OrgUnitSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = "directory.view"

    def get_queryset(self) -> Any:
        return OrgUnit.objects.order_by("path", "name")


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
        "Pass ``?commit=true`` to invite each new email (same accept link as a "
        "member invite) and update existing members' org unit and employee ref. "
        "Audited, and idempotent via the ``Idempotency-Key`` header."
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
