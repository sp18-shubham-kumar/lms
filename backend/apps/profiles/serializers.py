"""
Serializers for the profiles app.

Tracks, JobProfiles, ProfileRequirements, and ReadinessSnapshots.
"""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot, Track
from apps.skills.models import Skill

# Skill rubrics run 1..5 (SkillLevel); a requirement can't target a level outside them.
MIN_LEVEL = 1
MAX_LEVEL = 5


class TrackSerializer(serializers.ModelSerializer):
    """A career track (Backend, Design, Sales, ...)."""

    class Meta:
        model = Track
        fields = ["id", "tenant", "name", "created_at", "updated_at"]
        read_only_fields = ["id", "tenant", "created_at", "updated_at"]


class JobProfileSerializer(serializers.ModelSerializer):
    """
    A graded role definition within a track. ``status``/``version`` are server-managed.
    """

    class Meta:
        model = JobProfile
        fields = [
            "id",
            "tenant",
            "track",
            "grade",
            "title",
            "status",
            "version",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "status", "version", "created_at", "updated_at"]


class _VisibleSkillField(serializers.PrimaryKeyRelatedField):
    """
    Skill choices limited to globals + the current tenant's own skills. The default
    Skill manager is unscoped (seeding must read globals), so the plain field would
    accept another tenant's skill.
    """

    def get_queryset(self) -> Any:
        return Skill.objects.visible()


class ProfileRequirementSerializer(serializers.ModelSerializer):
    """A required skill level within a job profile."""

    skill: _VisibleSkillField = _VisibleSkillField()
    skill_name = serializers.CharField(source="skill.name", read_only=True)
    min_level = serializers.IntegerField(min_value=MIN_LEVEL, max_value=MAX_LEVEL)

    class Meta:
        model = ProfileRequirement
        fields = [
            "id",
            "tenant",
            "job_profile",
            "skill",
            "skill_name",
            "min_level",
            "criticality",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "tenant", "job_profile", "created_at", "updated_at"]


class ReadinessSnapshotSerializer(serializers.ModelSerializer):
    """Cached readiness result for a membership against a job profile."""

    display_name = serializers.SerializerMethodField(
        help_text="Display name of the membership's person."
    )

    class Meta:
        model = ReadinessSnapshot
        fields = [
            "id",
            "membership",
            "job_profile",
            "met",
            "total",
            "blocking_skill_ids",
            "job_profile_version",
            "computed_at",
            "display_name",
        ]
        read_only_fields = [
            "id",
            "met",
            "total",
            "blocking_skill_ids",
            "job_profile_version",
            "computed_at",
        ]

    def get_display_name(self, obj: ReadinessSnapshot) -> str:
        try:
            return obj.membership.person.display_name
        except Exception:
            return ""


# ─── Response shapes (OpenAPI documentation for the hand-built APIView payloads) ───


class GapItemSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    skill_name = serializers.CharField()
    criticality = serializers.CharField()
    min_level = serializers.IntegerField()
    current_level = serializers.IntegerField(
        allow_null=True, help_text="Verified assertion level, or null when none exists."
    )
    status = serializers.ChoiceField(choices=["met", "close", "not_started"])


class MeReadinessSerializer(serializers.Serializer):
    job_profile = serializers.UUIDField()
    readiness_pct = serializers.IntegerField(help_text="met / total * 100 for core requirements.")
    met = serializers.IntegerField()
    total = serializers.IntegerField()
    requirements = GapItemSerializer(many=True, help_text="Unmet first (smallest gap), met last.")


class MemberReadinessSerializer(MeReadinessSerializer):
    membership_id = serializers.UUIDField()
    display_name = serializers.CharField()


class HeatmapColumnSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    skill_name = serializers.CharField()


class HeatmapCellSerializer(serializers.Serializer):
    met = serializers.BooleanField()


class HeatmapRowSerializer(serializers.Serializer):
    membership_id = serializers.UUIDField()
    display_name = serializers.CharField()
    cells = HeatmapCellSerializer(many=True, help_text="One cell per column, in column order.")


class HeatmapSerializer(serializers.Serializer):
    columns = HeatmapColumnSerializer(many=True, help_text="Core requirements of the profile.")
    rows = HeatmapRowSerializer(many=True, help_text="Members of the org-unit subtree.")
