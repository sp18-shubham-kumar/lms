from __future__ import annotations

from rest_framework import serializers

from apps.authz.models import Role, RoleGrant


class RoleSerializer(serializers.ModelSerializer):
    """A role plus its capability keys."""

    capabilities = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ["id", "name", "is_system", "capabilities"]

    def get_capabilities(self, obj: Role) -> list[str]:
        return sorted(obj.capabilities.values_list("capability__key", flat=True))


class RoleWriteSerializer(serializers.Serializer):
    """Create or update a role. Capabilities are existing keys, replaced as a set."""

    name = serializers.CharField(max_length=100)
    capabilities = serializers.ListField(
        child=serializers.CharField(max_length=100),
        allow_empty=True,
    )


class RoleGrantSerializer(serializers.ModelSerializer):
    """A grant of a role to a principal. ``tenant`` is resolved server-side."""

    class Meta:
        model = RoleGrant
        fields = ["id", "principal_type", "principal_id", "role", "scope_type", "scope_id"]
        read_only_fields = ["id"]
