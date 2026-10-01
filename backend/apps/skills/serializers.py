from __future__ import annotations

from rest_framework import serializers

from apps.skills.models import (
    SelfDeclaredSkill,
    Skill,
    SkillDomain,
    SkillEdge,
    SkillLevel,
    TenantSkillOverride,
)


class SkillDomainSerializer(serializers.ModelSerializer):
    """A skill grouping. Global domains (``tenant`` NULL) are read-only to tenants."""

    class Meta:
        model = SkillDomain
        fields = ["id", "tenant", "name", "sort"]
        read_only_fields = ["id", "tenant"]


class SkillSerializer(serializers.ModelSerializer):
    """A versioned capability. ``tenant``/``status``/``version`` are server-managed."""

    class Meta:
        model = Skill
        fields = [
            "id",
            "tenant",
            "domain",
            "name",
            "slug",
            "external_code",
            "description",
            "status",
            "version",
        ]
        read_only_fields = ["id", "tenant", "status", "version"]


class SelfDeclaredSkillSerializer(serializers.ModelSerializer):
    """A caller's self-claim. ``membership``/``tenant`` are resolved server-side."""

    class Meta:
        model = SelfDeclaredSkill
        fields = ["id", "membership", "skill", "level", "note"]
        read_only_fields = ["id", "membership"]

    def validate_level(self, value: int | None) -> int | None:
        # Levels run 1..5 (per skill_level in the spec). Part B refines against a
        # skill's defined max level; for now enforce the 1..5 band.
        if value is not None and not (1 <= value <= 5):
            raise serializers.ValidationError("level must be between 1 and 5.")
        return value


class SkillLevelSerializer(serializers.ModelSerializer):
    """A single rung of a skill's rubric grid (level 1..5)."""

    class Meta:
        model = SkillLevel
        fields = [
            "id",
            "level",
            "title",
            "indicators",
            "evidence_kinds",
            "min_verifier_level",
            "validity_months",
        ]
        read_only_fields = ["id"]


class SkillLevelsReplaceSerializer(serializers.Serializer):
    """Request body for PUT ``/skills/{id}/levels/`` — replaces the whole rubric grid."""

    levels = SkillLevelSerializer(many=True)


class SkillEdgeSerializer(serializers.ModelSerializer):
    """A prerequisite/adjacent edge from one skill to another."""

    class Meta:
        model = SkillEdge
        fields = ["id", "from_skill", "to_skill", "kind"]
        read_only_fields = ["id", "from_skill"]


class TenantSkillOverrideSerializer(serializers.ModelSerializer):
    """A tenant's copy-on-write override of a skill (rename / relabel / hide)."""

    class Meta:
        model = TenantSkillOverride
        fields = ["id", "skill", "name", "status", "hidden"]
        read_only_fields = ["id", "skill"]
