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


def _add_member(tenant, email, cap_keys):
    from django.contrib.auth import get_user_model

    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from apps.identity.models import Membership
    from core.context import tenant_context

    Person = get_user_model()
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
        role = Role.objects.create(tenant=tenant, name="Role2", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)
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


@pytest.mark.django_db
def test_declare_skill_ties_to_caller_membership():
    from core.models import AuditLog

    tenant, _, membership = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    skill = _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/me/declarations/",
        {"skill": str(skill.id), "level": 3, "note": "confident"},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 201
    assert resp.json()["level"] == 3
    assert AuditLog.objects.filter(action="skill.declare").exists()


@pytest.mark.django_db
def test_duplicate_declaration_rejected():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    skill = _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}
    client.post(
        "/api/skills/me/declarations/", {"skill": str(skill.id), "level": 2}, format="json", **auth
    )
    dup = client.post(
        "/api/skills/me/declarations/", {"skill": str(skill.id), "level": 2}, format="json", **auth
    )
    assert dup.status_code == 400


@pytest.mark.django_db
def test_out_of_range_level_rejected():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    skill = _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.post(
        "/api/skills/me/declarations/",
        {"skill": str(skill.id), "level": 9},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 400


@pytest.mark.django_db
def test_list_returns_only_callers_declarations():
    from apps.skills.models import SelfDeclaredSkill
    from core.context import tenant_context

    tenant, _, membership_a = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    _, membership_b = _add_member(tenant, "b@acme.test", ["skill.claim.submit"])
    skill = _global_skill()
    with tenant_context(tenant.id):
        SelfDeclaredSkill.objects.create(
            tenant=tenant, membership=membership_b, skill=skill, level=4
        )

    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}
    client.post(
        "/api/skills/me/declarations/", {"skill": str(skill.id), "level": 2}, format="json", **auth
    )
    resp = client.get("/api/skills/me/declarations/", **auth)
    assert resp.status_code == 200
    rows = resp.json()["results"]
    membership_ids = {row["membership"] for row in rows}
    assert membership_ids == {str(membership_a.id)}  # only caller's, never member B's


@pytest.mark.django_db
def test_delete_own_and_cannot_delete_others():
    from apps.skills.models import SelfDeclaredSkill
    from core.context import tenant_context

    tenant, _, membership_a = _seed_tenant("acme", "a@acme.test", ["skill.claim.submit"])
    _, membership_b = _add_member(tenant, "b@acme.test", ["skill.claim.submit"])
    skill = _global_skill()
    with tenant_context(tenant.id):
        own = SelfDeclaredSkill.objects.create(
            tenant=tenant, membership=membership_a, skill=skill, level=2
        )
        other = SelfDeclaredSkill.objects.create(
            tenant=tenant, membership=membership_b, skill=skill, level=2
        )

    client = APIClient()
    token = _login(client, "a@acme.test")
    auth = {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}

    del_own = client.delete(f"/api/skills/me/declarations/{own.id}/", **auth)
    assert del_own.status_code == 204

    del_other = client.delete(f"/api/skills/me/declarations/{other.id}/", **auth)
    assert del_other.status_code == 404  # another member's declaration is invisible


@pytest.mark.django_db
def test_declaration_denied_without_capability():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", [])  # no skill.claim.submit
    _global_skill()
    client = APIClient()
    token = _login(client, "a@acme.test")
    resp = client.get(
        "/api/skills/me/declarations/",
        HTTP_AUTHORIZATION=f"Bearer {token}",
        HTTP_X_TENANT_ID=str(tenant.id),
    )
    assert resp.status_code == 403
