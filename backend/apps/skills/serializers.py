from __future__ import annotations

from rest_framework import serializers

from apps.skills.models import Skill, SkillDomain


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
