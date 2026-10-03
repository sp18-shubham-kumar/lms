"""The resource.edit capability reaches admins (new, existing and demo), and the demo library seeds."""

from __future__ import annotations

import importlib

import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.learning.tests.conftest import make_member, make_tenant

pytestmark = pytest.mark.django_db


def test_tenant_admin_role_includes_resource_edit():
    from apps.identity.provision import ADMIN_CAPABILITIES

    assert "resource.edit" in ADMIN_CAPABILITIES


def test_migration_grants_resource_edit_to_existing_taxonomy_editors():
    from apps.authz.models import RoleCapability, RoleGrant

    tenant = make_tenant("legacy")
    admin = make_member(tenant, "admin@legacy.test", ["directory.view", "taxonomy.edit"])
    learner = make_member(tenant, "learner@legacy.test", ["directory.view"])
    migration = importlib.import_module("apps.learning.migrations.0002_grant_resource_edit")

    # The historical registry the migration really runs against (plain managers).
    state_apps = (
        MigrationLoader(connection).project_state(("learning", "0002_grant_resource_edit")).apps
    )

    migration.grant(state_apps, None)
    migration.grant(state_apps, None)  # re-running is harmless

    granted = RoleCapability.all_tenants.filter(capability_id="resource.edit")
    role_ids = set(granted.values_list("role_id", flat=True))
    assert granted.count() == 1

    def role_of(member):
        return RoleGrant.all_tenants.get(principal_id=member.person.id).role_id

    assert role_ids == {role_of(admin)}
    assert role_of(learner) not in role_ids


def test_seed_demo_seeds_the_learning_library_idempotently():
    from apps.authz.models import RoleCapability
    from apps.identity.models import Tenant
    from apps.learning.models import LearningProgress, LearningResource, ResourceSkill

    call_command("seed_demo")
    call_command("seed_demo")

    acme = Tenant.objects.get(slug="acme")
    resources = LearningResource.all_tenants.filter(tenant=acme)
    assert resources.count() == 6
    assert resources.filter(status="published").count() == 6
    assert ResourceSkill.all_tenants.filter(tenant=acme).count() == 7
    progress = LearningProgress.all_tenants.get(tenant=acme)
    assert (progress.resource.title, progress.completed_modules) == (
        "Intermediate Python for Data",
        2,
    )
    admin_caps = set(
        RoleCapability.all_tenants.filter(tenant=acme, role__name="Admin").values_list(
            "capability__key", flat=True
        )
    )
    assert "resource.edit" in admin_caps
