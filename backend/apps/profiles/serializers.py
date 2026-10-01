"""
Serializers for the profiles app.

Tracks, JobProfiles, ProfileRequirements, and ReadinessSnapshots.
"""

from __future__ import annotations

from rest_framework import serializers

from apps.profiles.models import JobProfile, ProfileRequirement, ReadinessSnapshot, Track


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


class ProfileRequirementSerializer(serializers.ModelSerializer):
    """A required skill level within a job profile."""

    class Meta:
        model = ProfileRequirement
        fields = [
            "id",
            "tenant",
            "job_profile",
            "skill",
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
