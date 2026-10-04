from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.authz.models import Capability, Role, RoleGrant


class CapabilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Capability
        fields = ["key"]


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


ORG_UNIT_SCOPE = "org_unit"


class RoleGrantSerializer(serializers.ModelSerializer):
    """
    A grant of a role to a principal. ``tenant`` is resolved server-side.

    The principal must be an active member of the active tenant, an ``org_unit`` scope
    must name one of the tenant's org units, and the same (principal, role, scope) can
    only be granted once.
    """

    role_name = serializers.CharField(source="role.name", read_only=True)
    scope_type = serializers.ChoiceField(
        choices=[("", "Tenant-wide"), (ORG_UNIT_SCOPE, "Org unit")],
        required=False,
        allow_blank=True,
        default="",
    )

    class Meta:
        model = RoleGrant
        fields = [
            "id",
            "principal_type",
            "principal_id",
            "role",
            "role_name",
            "scope_type",
            "scope_id",
        ]
        read_only_fields = ["id", "principal_type"]

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        from apps.identity.models import Membership, OrgUnit

        principal_id = attrs["principal_id"]
        if not Membership.objects.filter(person_id=principal_id, status="active").exists():
            raise serializers.ValidationError(
                {"principal_id": "Not an active member of this organization."}
            )
        scope_type = attrs.get("scope_type", "")
        scope_id = attrs.get("scope_id")
        if scope_type == ORG_UNIT_SCOPE:
            if scope_id is None or not OrgUnit.objects.filter(id=scope_id).exists():
                raise serializers.ValidationError({"scope_id": "Unknown org unit."})
        elif scope_id is not None:
            raise serializers.ValidationError({"scope_id": "Set scope_type with a scope_id."})
        if RoleGrant.objects.filter(
            principal_type="person",
            principal_id=principal_id,
            role=attrs["role"],
            scope_type=scope_type,
            scope_id=scope_id,
        ).exists():
            raise serializers.ValidationError("This role is already granted with that scope.")
        return attrs
