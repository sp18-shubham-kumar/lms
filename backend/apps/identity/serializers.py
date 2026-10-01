from __future__ import annotations

from rest_framework import serializers

from apps.identity.models import Invitation, Membership, OrgUnit, Person, Tenant


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


class TenantProvisionSerializer(serializers.Serializer):
    """Body for creating a tenant and emailing its first admin."""

    name = serializers.CharField(max_length=255)
    slug = serializers.SlugField(max_length=50)
    admin_email = serializers.EmailField()


class InvitationCreateSerializer(serializers.Serializer):
    """Invite an email into a role in the active tenant. ``role`` is a name or id."""

    email = serializers.EmailField()
    role = serializers.CharField()


class InvitationSerializer(serializers.ModelSerializer):
    """A pending invitation. The accept token is not included."""

    role = serializers.SerializerMethodField()
    role_id = serializers.UUIDField(allow_null=True)

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "role_id", "status", "expires_at"]

    def get_role(self, obj: Invitation) -> str:
        role = obj.role
        return role.name if role is not None else ""


class InvitationAcceptSerializer(serializers.Serializer):
    """Consume an invitation token and set the person's password."""

    token = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


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
