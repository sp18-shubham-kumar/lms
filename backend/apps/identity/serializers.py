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


# ─── Response shapes (OpenAPI documentation for the hand-built APIView payloads) ───


class LoginResponseSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="JWT access token. Send as `Authorization: Bearer`.")
    refresh = serializers.CharField(help_text="JWT refresh token for /api/auth/token/refresh/.")
    memberships = MembershipSummarySerializer(
        many=True, help_text="Tenants the person can act in. Use a `tenant_id` as X-Tenant-Id."
    )


class SessionSerializer(serializers.Serializer):
    person = PersonSummarySerializer()
    tenant = TenantSummarySerializer()
    capabilities = serializers.ListField(
        child=serializers.CharField(), help_text="Capability keys held in the active tenant."
    )
    memberships = MembershipSummarySerializer(many=True)


class InvitationPayloadSerializer(serializers.Serializer):
    """An invitation as returned by create/resend. ``token`` is shown exactly once."""

    id = serializers.UUIDField()
    email = serializers.EmailField()
    role = serializers.CharField()
    role_id = serializers.UUIDField(allow_null=True)
    status = serializers.ChoiceField(choices=Invitation.Status.choices)
    expires_at = serializers.DateTimeField()
    token = serializers.CharField(required=False, help_text="Raw accept token, returned once.")


class InvitationAcceptResponseSerializer(serializers.Serializer):
    email = serializers.EmailField()
    tenant_id = serializers.UUIDField()


class _ProvisionedTenantSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    slug = serializers.SlugField()


class TenantProvisionResponseSerializer(serializers.Serializer):
    tenant = _ProvisionedTenantSerializer()
    admin = PersonSummarySerializer()
    role = serializers.CharField(help_text="Name of the role granted to the first admin.")
    invitation = InvitationPayloadSerializer()


# ─── Learner profile ───


class _ProfileOrgUnitSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    path = serializers.CharField()


class ProfileDeclaredSkillSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    skill_name = serializers.CharField()
    level = serializers.IntegerField(allow_null=True)
    note = serializers.CharField(allow_blank=True)


class ProfileVerifiedSkillSerializer(serializers.Serializer):
    skill_id = serializers.UUIDField()
    skill_name = serializers.CharField()
    level = serializers.IntegerField()
    verified_at = serializers.DateTimeField(allow_null=True)


class ProfileReadinessSerializer(serializers.Serializer):
    job_profile_id = serializers.UUIDField()
    job_profile_name = serializers.CharField()
    met = serializers.IntegerField()
    total = serializers.IntegerField()
    readiness_pct = serializers.IntegerField()
    computed_at = serializers.DateTimeField()


class PersonProfileSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    email = serializers.EmailField()
    display_name = serializers.CharField()
    status = serializers.CharField()
    joined_at = serializers.DateTimeField(allow_null=True)
    org_unit = _ProfileOrgUnitSerializer(allow_null=True)
    declared = ProfileDeclaredSkillSerializer(many=True)
    verified = ProfileVerifiedSkillSerializer(many=True)
    readiness = ProfileReadinessSerializer(
        many=True,
        help_text="Readiness snapshots; only for the caller's own profile or with report.org.view.",
    )
