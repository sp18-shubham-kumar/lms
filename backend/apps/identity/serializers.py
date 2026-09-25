from __future__ import annotations

from rest_framework import serializers

from apps.identity.models import Membership, Person


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
