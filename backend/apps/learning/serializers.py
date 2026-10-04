from __future__ import annotations

from typing import Any

from django.db import transaction
from rest_framework import serializers

from apps.learning.models import LearningProgress, LearningResource, ResourceSkill
from apps.skills.serializers import VisibleSkillField


class ResourceSkillSerializer(serializers.ModelSerializer):
    """A skill the resource teaches, and the level (1..5) it teaches toward."""

    # Only globals and the current tenant's own skills may be linked.
    skill: VisibleSkillField = VisibleSkillField()
    skill_name = serializers.CharField(source="skill.name", read_only=True)

    class Meta:
        model = ResourceSkill
        fields = ["skill", "skill_name", "level"]

    def validate_level(self, value: int) -> int:
        if not (1 <= value <= 5):
            raise serializers.ValidationError("level must be between 1 and 5.")
        return value


class LearningResourceSerializer(serializers.ModelSerializer):
    """A learning resource with its skill links. ``skills`` is replaced wholesale on write."""

    skills = ResourceSkillSerializer(many=True, source="skill_links", required=False)

    class Meta:
        model = LearningResource
        fields = [
            "id",
            "title",
            "kind",
            "url",
            "provider",
            "description",
            "module_count",
            "duration_minutes",
            "status",
            "skills",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate_skills(self, value: list[dict[str, Any]]) -> list[dict[str, Any]]:
        skill_ids = [link["skill"].id for link in value]
        if len(skill_ids) != len(set(skill_ids)):
            raise serializers.ValidationError("A skill can be linked only once per resource.")
        return value

    def _replace_links(self, resource: LearningResource, links: list[dict[str, Any]]) -> None:
        # An updated instance was loaded with ``prefetch_related("skill_links__skill")``;
        # drop that cache so later reads (the audit record) see the new links.
        getattr(resource, "_prefetched_objects_cache", {}).pop("skill_links", None)
        ResourceSkill.objects.filter(resource=resource).delete()
        ResourceSkill.objects.bulk_create(
            ResourceSkill(
                tenant_id=resource.tenant_id,
                resource=resource,
                skill=link["skill"],
                level=link["level"],
            )
            for link in links
        )

    @transaction.atomic
    def create(self, validated_data: dict[str, Any]) -> LearningResource:
        links = validated_data.pop("skill_links", [])
        resource = LearningResource.objects.create(**validated_data)
        self._replace_links(resource, links)
        return resource

    @transaction.atomic
    def update(
        self, instance: LearningResource, validated_data: dict[str, Any]
    ) -> LearningResource:
        links = validated_data.pop("skill_links", None)
        resource = super().update(instance, validated_data)
        if links is not None:
            self._replace_links(resource, links)
        return resource


class ResourceSummarySerializer(serializers.ModelSerializer):
    """The resource fields a progress row or recommendation needs to render a card."""

    class Meta:
        model = LearningResource
        fields = [
            "id",
            "title",
            "kind",
            "url",
            "provider",
            "module_count",
            "duration_minutes",
            "status",
        ]
        read_only_fields = fields


class LearningProgressSerializer(serializers.ModelSerializer):
    """The caller's progress through one resource."""

    resource_detail = ResourceSummarySerializer(source="resource", read_only=True)

    class Meta:
        model = LearningProgress
        fields = [
            "id",
            "resource",
            "resource_detail",
            "status",
            "completed_modules",
            "started_at",
            "completed_at",
            "updated_at",
        ]
        read_only_fields = fields


class ProgressStartSerializer(serializers.Serializer):
    """Request body for ``POST /learning/me/progress/`` — start a resource."""

    resource: serializers.PrimaryKeyRelatedField[LearningResource] = (
        serializers.PrimaryKeyRelatedField(queryset=LearningResource.objects.none())
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Scoped manager: a resource from another tenant is simply "not found".
        self.fields["resource"].queryset = LearningResource.objects.all()  # type: ignore[attr-defined]


class ProgressUpdateSerializer(serializers.Serializer):
    """Request body for ``PATCH /learning/me/progress/{id}/`` — set modules and/or status."""

    completed_modules = serializers.IntegerField(required=False, min_value=0)
    status = serializers.ChoiceField(choices=LearningProgress.STATUS_CHOICES, required=False)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("Provide completed_modules and/or status.")
        return attrs


class RecommendedResourceSerializer(serializers.Serializer):
    resource = ResourceSummarySerializer()
    target_level = serializers.IntegerField()
    progress = LearningProgressSerializer(allow_null=True)


class RecommendationGapSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    skill_name = serializers.CharField()
    criticality = serializers.CharField()
    min_level = serializers.IntegerField()
    current_level = serializers.IntegerField(allow_null=True)
    resources = RecommendedResourceSerializer(many=True)
    refreshers = RecommendedResourceSerializer(many=True)


class RecommendationsSerializer(serializers.Serializer):
    job_profile = serializers.UUIDField()
    gaps = RecommendationGapSerializer(many=True)
