import pytest
from rest_framework.test import APIClient


def _seed_tenant(slug, email, cap_keys):
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
    return tenant, person, membership


def _add_member(tenant, email, org_unit=None):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(
            person=person, tenant=tenant, status="active", org_unit=org_unit
        )
    return person, membership


def _login(client, email):
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    return body["access"]


def _global_skill(slug="sql"):
    from apps.skills.models import Skill, SkillDomain

    gd = SkillDomain.objects.create(tenant=None, name="Global")
    return Skill.objects.create(
        tenant=None, domain=gd, name=slug.upper(), slug=slug, status="published"
    )


def _declare(tenant, membership, skill, level):
    from apps.skills.models import SelfDeclaredSkill
    from core.context import tenant_context

    with tenant_context(tenant.id):
        SelfDeclaredSkill.objects.create(
            tenant=tenant, membership=membership, skill=skill, level=level
        )


@pytest.mark.django_db
def test_filter_by_skill_returns_only_matching_and_is_isolated():
    tenant_a, _, membership_a = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    _, membership_a2 = _add_member(tenant_a, "a2@acme.test")
    tenant_b, _, membership_b = _seed_tenant("northwind", "b@nw.test", ["directory.view"])

    skill = _global_skill()
    _declare(tenant_a, membership_a, skill, 3)
    # Tenant B member also declares the same global skill — must never leak into A.
    _declare(tenant_b, membership_b, skill, 3)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/identity/people/?skill={skill.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert emails == {"a@acme.test"}  # a2 did not declare; B never leaks


@pytest.mark.django_db
def test_filter_by_level_requires_minimum():
    tenant_a, _, membership_a = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    _, membership_a2 = _add_member(tenant_a, "a2@acme.test")
    skill = _global_skill()
    _declare(tenant_a, membership_a, skill, 2)
    _declare(tenant_a, membership_a2, skill, 4)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/identity/people/?skill={skill.id}&level=3",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert emails == {"a2@acme.test"}  # only level >= 3


@pytest.mark.django_db
def test_filter_by_org_unit_returns_subtree_and_is_isolated():
    from apps.identity.models import OrgUnit
    from core.context import tenant_context

    tenant_a, _, membership_a = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    with tenant_context(tenant_a.id):
        parent = OrgUnit.objects.create(tenant=tenant_a, name="Eng", path="eng")
        child = OrgUnit.objects.create(
            tenant=tenant_a, name="Platform", path="eng.platform", parent=parent
        )
        other = OrgUnit.objects.create(tenant=tenant_a, name="Sales", path="sales")

    _, member_parent = _add_member(tenant_a, "parent@acme.test", org_unit=parent)
    _, member_child = _add_member(tenant_a, "child@acme.test", org_unit=child)
    _, member_other = _add_member(tenant_a, "sales@acme.test", org_unit=other)

    # Tenant B has an org unit with a colliding path prefix; must never leak.
    tenant_b, _, _ = _seed_tenant("northwind", "b@nw.test", ["directory.view"])
    with tenant_context(tenant_b.id):
        b_unit = OrgUnit.objects.create(tenant=tenant_b, name="Eng", path="eng")
    _add_member(tenant_b, "beng@nw.test", org_unit=b_unit)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/identity/people/?org_unit={parent.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert emails == {"parent@acme.test", "child@acme.test"}  # subtree, not sales, not B


@pytest.mark.django_db
def test_filters_combine_with_and():
    from apps.identity.models import OrgUnit
    from core.context import tenant_context

    tenant_a, _, membership_a = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    with tenant_context(tenant_a.id):
        unit = OrgUnit.objects.create(tenant=tenant_a, name="Eng", path="eng")
    _, in_unit = _add_member(tenant_a, "inunit@acme.test", org_unit=unit)
    _, no_unit = _add_member(tenant_a, "nounit@acme.test")

    skill = _global_skill()
    _declare(tenant_a, in_unit, skill, 4)
    _declare(tenant_a, no_unit, skill, 4)

    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        f"/api/identity/people/?skill={skill.id}&org_unit={unit.id}",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant_a.id),
    )
    assert resp.status_code == 200
    emails = {row["email"] for row in resp.json()["results"]}
    assert emails == {"inunit@acme.test"}  # has skill AND in unit
