from __future__ import annotations

from rest_framework import serializers

from apps.skills.models import SelfDeclaredSkill, Skill, SkillDomain


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
