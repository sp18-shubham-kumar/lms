from __future__ import annotations

from typing import Any

from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.views import APIView

from apps.skills.models import Skill, SkillDomain
from apps.skills.serializers import SkillDomainSerializer, SkillSerializer
from core.permissions import HasCapability

READ_CAPABILITY = "directory.view"


@extend_schema(tags=["Skills"])
class SkillDomainViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve skill domains visible to the tenant (globals + tenant rows)."""

    serializer_class = SkillDomainSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = READ_CAPABILITY

    def get_queryset(self) -> Any:
        # .visible() = globals (tenant NULL) ∪ current tenant rows (fail-closed).
        return SkillDomain.objects.visible().order_by("sort", "name")


@extend_schema(tags=["Skills"])
class SkillViewSet(viewsets.ReadOnlyModelViewSet):
    """List/retrieve skills visible to the tenant (globals + tenant rows)."""

    serializer_class = SkillSerializer
    permission_classes = [*APIView.permission_classes, HasCapability]
    required_capability = READ_CAPABILITY

    def get_queryset(self) -> Any:
        return Skill.objects.visible().select_related("domain").order_by("name")
