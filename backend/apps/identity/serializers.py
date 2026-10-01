from __future__ import annotations

from rest_framework import serializers

from apps.identity.models import Membership, OrgUnit, Person, Tenant


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class MembershipSummarySerializer(serializers.ModelSerializer):
    tenant_id = serializers.UUIDField(source="tenant.id")
    slug = serializers.CharField(source="tenant.slug")
    name = serializers.CharField(source="tenant.name")
    accent_color = serializers.CharField(source="tenant.accent_color")

    class Meta:
        model = Membership
        fields = ["tenant_id", "slug", "name", "accent_color"]


class PersonSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "email", "display_name"]


class TenantSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "slug", "accent_color", "logo_url"]


class PersonDirectorySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="person.id")
    email = serializers.EmailField(source="person.email")
    display_name = serializers.CharField(source="person.display_name")
    org_unit = serializers.CharField(source="org_unit.name", default=None)

    class Meta:
        model = Membership
        fields = ["id", "email", "display_name", "org_unit", "status"]


class OrgUnitSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrgUnit
        fields = ["id", "name", "path", "parent"]
