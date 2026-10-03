"""
Framework authoring + verification API: tenant domains, version immutability,
versions/new-version, edge visibility, and the verifier claim queue.
"""

import pytest
from rest_framework.test import APIClient

AUTHOR_CAPS = ["directory.view", "taxonomy.edit"]


def _seed_tenant(slug, email, cap_keys):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership, Tenant
    from core.context import tenant_context

    Person = get_user_model()
    tenant = Tenant.objects.create(slug=slug, name=slug.title(), status="active", plan="pro")
    person = Person.objects.create_user(email=email, display_name=email, password="pw-12345")
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
    _grant(tenant, person, cap_keys)
    return tenant, person, membership


def _add_member(tenant, email, cap_keys):
    from django.contrib.auth import get_user_model

    from apps.identity.models import Membership
    from core.context import tenant_context

    person = get_user_model().objects.create_user(
        email=email, display_name=email.split("@")[0].title(), password="pw-12345"
    )
    with tenant_context(tenant.id):
        membership = Membership.objects.create(person=person, tenant=tenant, status="active")
    _grant(tenant, person, cap_keys)
    return person, membership


def _grant(tenant, person, cap_keys):
    from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
    from core.context import tenant_context

    with tenant_context(tenant.id):
        role = Role.objects.create(tenant=tenant, name=f"Role {person.email}", is_system=True)
        RoleGrant.objects.create(
            tenant=tenant, principal_type="person", principal_id=person.id, role=role
        )
        for key in cap_keys:
            cap, _ = Capability.objects.get_or_create(key=key)
            RoleCapability.objects.create(tenant=tenant, role=role, capability=cap)


def _auth(email, tenant):
    client = APIClient()
    body = client.post(
        "/api/auth/login/", {"email": email, "password": "pw-12345"}, format="json"
    ).json()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {body['access']}", HTTP_X_TENANT_ID=str(tenant.id)
    )
    return client


def _tenant_skill(tenant, slug="sql", status="draft"):
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    with tenant_context(tenant.id):
        domain = SkillDomain.objects.create(tenant=tenant, name=f"D {slug}")
        return Skill.objects.create(
            tenant=tenant, domain=domain, name=slug.upper(), slug=slug, status=status
        )


def _global_skill():
    from apps.skills.models import Skill, SkillDomain

    domain = SkillDomain.objects.create(tenant=None, name="Global")
    return Skill.objects.create(
        tenant=None, domain=domain, name="Global SQL", slug="global-sql", status="published"
    )


# --- Domains ----------------------------------------------------------------


@pytest.mark.django_db
def test_create_domain_is_tenant_owned_and_audited():
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    client = _auth("a@acme.test", tenant)
    resp = client.post("/api/skills/domains/", {"name": "Analytics", "sort": 2}, format="json")
    assert resp.status_code == 201
    assert resp.json()["tenant"] == str(tenant.id)
    assert AuditLog.objects.filter(action="skill.domain.create").exists()

    renamed = client.patch(
        f"/api/skills/domains/{resp.json()['id']}/", {"name": "Data analytics"}, format="json"
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Data analytics"


@pytest.mark.django_db
def test_domain_write_denied_without_taxonomy_edit():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    client = _auth("a@acme.test", tenant)
    resp = client.post("/api/skills/domains/", {"name": "Nope"}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_global_domain_is_read_only_to_tenants():
    from apps.skills.models import SkillDomain

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    gd = SkillDomain.objects.create(tenant=None, name="Global")
    client = _auth("a@acme.test", tenant)
    resp = client.patch(f"/api/skills/domains/{gd.id}/", {"name": "hacked"}, format="json")
    assert resp.status_code == 403
    gd.refresh_from_db()
    assert gd.name == "Global"


@pytest.mark.django_db
def test_other_tenants_domain_is_invisible():
    tenant_a, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    tenant_b, _, _ = _seed_tenant("nw", "b@nw.test", AUTHOR_CAPS)
    created = _auth("a@acme.test", tenant_a).post(
        "/api/skills/domains/", {"name": "Acme only"}, format="json"
    )
    client_b = _auth("b@nw.test", tenant_b)
    names = {d["name"] for d in client_b.get("/api/skills/domains/").json()["results"]}
    assert "Acme only" not in names
    resp = client_b.patch(
        f"/api/skills/domains/{created.json()['id']}/", {"name": "x"}, format="json"
    )
    assert resp.status_code == 404


# --- Versioning -------------------------------------------------------------


@pytest.mark.django_db
def test_published_skill_cannot_be_edited_in_place():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    skill = _tenant_skill(tenant, status="published")
    client = _auth("a@acme.test", tenant)

    patch = client.patch(f"/api/skills/{skill.id}/", {"name": "Renamed"}, format="json")
    assert patch.status_code == 400
    assert "new version" in str(patch.json()["error"]["detail"])

    levels = client.put(
        f"/api/skills/{skill.id}/levels/", {"levels": [{"level": 1}]}, format="json"
    )
    assert levels.status_code == 400


@pytest.mark.django_db
def test_tenant_cannot_rewrite_a_global_rubric():
    from apps.skills.models import SkillLevel

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    gs = _global_skill()
    client = _auth("a@acme.test", tenant)
    resp = client.put(f"/api/skills/{gs.id}/levels/", {"levels": [{"level": 1}]}, format="json")
    assert resp.status_code == 403
    assert not SkillLevel.objects.filter(skill=gs).exists()


@pytest.mark.django_db
def test_new_version_copies_rubric_and_lists_versions():
    from apps.skills.models import SkillLevel
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    skill = _tenant_skill(tenant)
    SkillLevel.objects.create(skill=skill, level=1, title="Aware")
    client = _auth("a@acme.test", tenant)

    assert client.post(f"/api/skills/{skill.id}/publish/").status_code == 200
    resp = client.post(f"/api/skills/{skill.id}/new-version/")
    assert resp.status_code == 201
    draft = resp.json()
    assert draft["version"] == 2
    assert draft["status"] == "draft"
    assert SkillLevel.objects.filter(skill_id=draft["id"], title="Aware").exists()
    assert AuditLog.objects.filter(action="skill.new_version").exists()

    versions = client.get(f"/api/skills/{draft['id']}/versions/").json()["versions"]
    assert [(v["version"], v["status"]) for v in versions] == [(2, "draft"), (1, "published")]


@pytest.mark.django_db
def test_new_version_requires_a_published_tenant_skill():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    client = _auth("a@acme.test", tenant)
    draft = _tenant_skill(tenant)
    assert client.post(f"/api/skills/{draft.id}/new-version/").status_code == 400
    assert client.post(f"/api/skills/{_global_skill().id}/new-version/").status_code == 403


@pytest.mark.django_db
def test_new_version_denied_without_taxonomy_edit():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    skill = _tenant_skill(tenant, status="published")
    client = _auth("a@acme.test", tenant)
    assert client.post(f"/api/skills/{skill.id}/new-version/").status_code == 403


# --- Edges ------------------------------------------------------------------


@pytest.mark.django_db
def test_global_skill_edges_hide_other_tenants_edges_and_reject_writes():
    from apps.skills.models import SkillEdge

    tenant_a, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    tenant_b, _, _ = _seed_tenant("nw", "b@nw.test", AUTHOR_CAPS)
    gs = _global_skill()
    target = _tenant_skill(tenant_b, slug="py")
    SkillEdge.objects.create(tenant=tenant_b, from_skill=gs, to_skill=target, kind="adjacent")

    client_a = _auth("a@acme.test", tenant_a)
    assert client_a.get(f"/api/skills/{gs.id}/edges/").json()["edges"] == []
    resp = client_a.post(
        f"/api/skills/{gs.id}/edges/",
        {"to_skill": str(_tenant_skill(tenant_a).id), "kind": "adjacent"},
        format="json",
    )
    assert resp.status_code == 403


# --- Claim queue ------------------------------------------------------------


def _claim(membership, skill, level=2):
    from apps.skills.models import SelfDeclaredSkill
    from core.context import tenant_context

    with tenant_context(membership.tenant_id):
        return SelfDeclaredSkill.objects.create(
            tenant_id=membership.tenant_id, membership=membership, skill=skill, level=level
        )


@pytest.mark.django_db
def test_verifier_sees_pending_claims_with_names():
    tenant, _, _ = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    _, member = _add_member(tenant, "bob@acme.test", ["skill.claim.submit"])
    skill = _tenant_skill(tenant)
    _claim(member, skill, level=3)

    rows = _auth("v@acme.test", tenant).get("/api/skills/claims/").json()["results"]
    assert len(rows) == 1
    assert rows[0]["person_name"] == "Bob"
    assert rows[0]["skill_name"] == "SQL"
    assert rows[0]["level"] == 3
    assert rows[0]["review_status"] == "pending"


@pytest.mark.django_db
def test_claim_queue_denied_without_skill_verify():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    assert _auth("a@acme.test", tenant).get("/api/skills/claims/").status_code == 403


@pytest.mark.django_db
def test_claim_queue_is_tenant_isolated():
    tenant_a, _, _ = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    tenant_b, _, _ = _seed_tenant("nw", "w@nw.test", ["skill.verify"])
    _, member_b = _add_member(tenant_b, "bob@nw.test", [])
    claim = _claim(member_b, _tenant_skill(tenant_b))

    client_a = _auth("v@acme.test", tenant_a)
    assert client_a.get("/api/skills/claims/?status=all").json()["results"] == []
    resp = client_a.post(f"/api/skills/claims/{claim.id}/verify/", {"level": 2}, format="json")
    assert resp.status_code == 404


@pytest.mark.django_db
def test_verify_claim_records_assertion_and_closes_claim():
    from apps.skills.models import SelfDeclaredSkill, SkillAssertion
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, verifier, _ = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    _, member = _add_member(tenant, "bob@acme.test", [])
    skill = _tenant_skill(tenant, status="published")
    claim = _claim(member, skill, level=3)

    client = _auth("v@acme.test", tenant)
    resp = client.post(
        f"/api/skills/claims/{claim.id}/verify/", {"level": 2, "note": "Pairing"}, format="json"
    )
    assert resp.status_code == 201
    assert resp.json()["level"] == 2
    with tenant_context(tenant.id):
        assertion = SkillAssertion.objects.get(membership=member, skill=skill)
        claim = SelfDeclaredSkill.objects.get(id=claim.id)
    assert assertion.verified_by_id == verifier.id
    assert assertion.skill_version == skill.version
    assert claim.review_status == "verified"
    assert claim.reviewed_by_id == verifier.id
    assert AuditLog.objects.filter(action="skill.assertion.record").exists()

    assert client.get("/api/skills/claims/").json()["results"] == []
    again = client.post(f"/api/skills/claims/{claim.id}/verify/", {"level": 2}, format="json")
    assert again.status_code == 400


@pytest.mark.django_db
def test_reject_claim_requires_reason_and_records_no_assertion():
    from apps.skills.models import SkillAssertion
    from core.context import tenant_context
    from core.models import AuditLog

    tenant, _, _ = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    _, member = _add_member(tenant, "bob@acme.test", ["skill.claim.submit"])
    claim = _claim(member, _tenant_skill(tenant))
    client = _auth("v@acme.test", tenant)

    assert (
        client.post(f"/api/skills/claims/{claim.id}/reject/", {}, format="json").status_code == 400
    )
    resp = client.post(
        f"/api/skills/claims/{claim.id}/reject/", {"note": "No evidence yet"}, format="json"
    )
    assert resp.status_code == 200
    assert resp.json()["review_status"] == "rejected"
    with tenant_context(tenant.id):
        assert not SkillAssertion.objects.filter(membership=member).exists()
    assert AuditLog.objects.filter(action="skill.claim.reject").exists()

    # The member sees the outcome on their own declaration.
    mine = _auth("bob@acme.test", tenant).get("/api/skills/me/declarations/").json()["results"]
    assert mine[0]["review_status"] == "rejected"
    assert mine[0]["review_note"] == "No evidence yet"


@pytest.mark.django_db
def test_verifier_cannot_review_own_claim():
    tenant, _, membership = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    claim = _claim(membership, _tenant_skill(tenant))
    client = _auth("v@acme.test", tenant)
    resp = client.post(f"/api/skills/claims/{claim.id}/verify/", {"level": 4}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_claim_queue_rejects_unknown_status_filter():
    tenant, _, _ = _seed_tenant("acme", "v@acme.test", ["skill.verify"])
    resp = _auth("v@acme.test", tenant).get("/api/skills/claims/?status=bogus")
    assert resp.status_code == 400


# --- Overrides --------------------------------------------------------------


@pytest.mark.django_db
def test_override_list_keeps_hidden_skills_reachable_and_is_isolated():
    tenant_a, _, _ = _seed_tenant("acme", "a@acme.test", AUTHOR_CAPS)
    tenant_b, _, _ = _seed_tenant("nw", "b@nw.test", AUTHOR_CAPS)
    gs = _global_skill()
    client_a = _auth("a@acme.test", tenant_a)
    hidden = client_a.post(f"/api/skills/{gs.id}/override/", {"hidden": True}, format="json")
    assert hidden.status_code == 200

    # Hidden from skill reads, but listed (with its real name) under overrides.
    assert str(gs.id) not in {s["id"] for s in client_a.get("/api/skills/").json()["results"]}
    rows = client_a.get("/api/skills/overrides/").json()["results"]
    assert [(r["skill"], r["skill_name"], r["hidden"]) for r in rows] == [
        (str(gs.id), "Global SQL", True)
    ]

    assert _auth("b@nw.test", tenant_b).get("/api/skills/overrides/").json()["results"] == []


@pytest.mark.django_db
def test_override_list_denied_without_taxonomy_edit():
    tenant, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view"])
    assert _auth("a@acme.test", tenant).get("/api/skills/overrides/").status_code == 403
