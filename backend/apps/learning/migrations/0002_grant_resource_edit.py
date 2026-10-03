"""
Seed the ``resource.edit`` capability and grant it to every existing role that can
already edit the taxonomy (tenant admins), so tenants provisioned before the
learning app can manage resources without a manual role edit.
"""

from django.db import migrations

CAPABILITY = "resource.edit"
GRANTED_ALONGSIDE = "taxonomy.edit"


def grant(apps, schema_editor):  # type: ignore[no-untyped-def]
    Capability = apps.get_model("authz", "Capability")
    RoleCapability = apps.get_model("authz", "RoleCapability")

    Capability.objects.get_or_create(key=CAPABILITY)
    for rc in RoleCapability.objects.filter(capability_id=GRANTED_ALONGSIDE):
        RoleCapability.objects.get_or_create(
            tenant_id=rc.tenant_id, role_id=rc.role_id, capability_id=CAPABILITY
        )


def revoke(apps, schema_editor):  # type: ignore[no-untyped-def]
    apps.get_model("authz", "RoleCapability").objects.filter(capability_id=CAPABILITY).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("learning", "0001_initial"),
        ("authz", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
