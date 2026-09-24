"""Core, non-domain endpoints (health, readiness)."""

from __future__ import annotations

from django.db import connection
from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    """Liveness/readiness probe. Public (no auth), checks DB connectivity."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        responses={200: {"type": "object", "example": {"status": "ok", "database": "ok"}}}
    )
    def get(self, request: Request) -> Response:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            database = "ok"
        except Exception:  # pragma: no cover - only when DB is down
            database = "error"
        return Response({"status": "ok", "database": database})
