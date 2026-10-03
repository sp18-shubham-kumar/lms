"""Fixtures for the learning app: two tenants, a learner and an editor, some skills."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from rest_framework.test import APIClient

LEARNER_CAPS = ["directory.view", "skill.claim.submit"]
EDITOR_CAPS = ["directory.view", "skill.claim.submit", "resource.edit"]
PASSWORD = "pw-12345"


@dataclass
class Member:
    tenant: Any
    person: Any
    membership: Any

    def client(self) -> APIClient:
        client = APIClient()
        access = client.post(
            "/api/auth/login/",
            {"email": self.person.email, "password": PASSWORD},
            format="json",
        ).json()["access"]
        client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {access}", HTTP_X_TENANT_ID=str(self.tenant.id)
        )
        return client


def make_tenant(slug: str) -> Any:
    from apps.identity.models import Tenant

    return Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")


def make_member(tenant: Any, email: str, caps: list[str]) -> Member:
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership
    from core.context import tenant_context

    person = get_user_model().objects.create_user(
        email=email, display_name=email, password=PASSWORD
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name=f"Role {email}")
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in caps:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return Member(tenant, person, membership)


def make_resource(tenant: Any, title: str, links: list[tuple[Any, int]], **fields: Any) -> Any:
    from apps.learning.models import LearningResource, ResourceSkill
    from core.context import tenant_context

    fields.setdefault("status", "published")
    fields.setdefault("module_count", 4)
    with tenant_context(tenant.id):
        resource = LearningResource.objects.create(tenant=tenant, title=title, **fields)
        for skill, level in links:
            ResourceSkill.objects.create(tenant=tenant, resource=resource, skill=skill, level=level)
    return resource


@pytest.fixture
def acme() -> Any:
    return make_tenant("acme")


@pytest.fixture
def globex() -> Any:
    return make_tenant("globex")


@pytest.fixture
def learner(acme: Any) -> Member:
    return make_member(acme, "learner@acme.test", LEARNER_CAPS)


@pytest.fixture
def editor(acme: Any) -> Member:
    return make_member(acme, "editor@acme.test", EDITOR_CAPS)


@pytest.fixture
def skills() -> dict[str, Any]:
    """Global (tenant NULL) skills, shared by every tenant."""
    from apps.skills.models import Skill, SkillDomain

    domain = SkillDomain.objects.create(tenant=None, name="Data")
    return {
        slug: Skill.objects.create(
            tenant=None, domain=domain, name=slug.upper(), slug=slug, status="published"
        )
        for slug in ("sql", "python", "dbt")
    }
