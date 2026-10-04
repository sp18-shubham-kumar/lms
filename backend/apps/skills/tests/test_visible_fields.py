"""
Skill/domain references in write payloads resolve through ``.visible()``.

Globals and the caller's own tenant are accepted; another tenant's skill or domain
is answered as if it didn't exist (400), never silently linked.
"""

from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.skills.tests.test_assertions import _login, _seed_tenant, _tenant_skill

pytestmark = pytest.mark.django_db


def _auth(tenant, email):
    token = _login(APIClient(), email)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}", "HTTP_X_TENANT_ID": str(tenant.id)}


def test_assertion_rejects_another_tenants_skill():
    from apps.skills.models import SkillAssertion

    acme, _, membership = _seed_tenant("acme", "a@acme.test", ["skill.verify"])
    globex, _, _ = _seed_tenant("globex", "g@globex.test", ["skill.verify"])
    foreign = _tenant_skill(globex)

    resp = APIClient().post(
        "/api/skills/assertions/",
        {"membership": str(membership.id), "skill": str(foreign.id), "level": 2},
        format="json",
        **_auth(acme, "a@acme.test"),
    )

    assert resp.status_code == 400, resp.json()
    assert "Unknown skill." in str(resp.json())
    assert not SkillAssertion.all_tenants.exists()


def test_assertion_rejects_a_level_of_a_different_skill():
    from apps.skills.models import SkillAssertion, SkillLevel

    acme, _, membership = _seed_tenant("acme", "a@acme.test", ["skill.verify"])
    sql = _tenant_skill(acme, slug="sql")
    python = _tenant_skill(acme, slug="python")
    python_l2 = SkillLevel.objects.create(skill=python, level=2, title="Python L2")

    resp = APIClient().post(
        "/api/skills/assertions/",
        {
            "membership": str(membership.id),
            "skill": str(sql.id),
            "level": 2,
            "skill_level": str(python_l2.id),
        },
        format="json",
        **_auth(acme, "a@acme.test"),
    )

    assert resp.status_code == 400, resp.json()
    assert "This level belongs to a different skill." in str(resp.json())
    assert not SkillAssertion.all_tenants.exists()


def test_create_skill_rejects_another_tenants_domain():
    from apps.skills.models import Skill, SkillDomain
    from core.context import tenant_context

    acme, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    globex, _, _ = _seed_tenant("globex", "g@globex.test", ["directory.view"])
    with tenant_context(globex.id):
        foreign_domain = SkillDomain.objects.create(tenant=globex, name="Globex only")

    resp = APIClient().post(
        "/api/skills/",
        {"domain": str(foreign_domain.id), "name": "dbt", "slug": "dbt"},
        format="json",
        **_auth(acme, "a@acme.test"),
    )

    assert resp.status_code == 400, resp.json()
    assert "Unknown skill domain." in str(resp.json())
    # Skill.objects is unscoped (GlobalOrTenantManager), so this sees every tenant.
    assert not Skill.objects.filter(slug="dbt").exists()


def test_add_edge_rejects_another_tenants_skill():
    from apps.skills.models import SkillEdge

    acme, _, _ = _seed_tenant("acme", "a@acme.test", ["directory.view", "taxonomy.edit"])
    globex, _, _ = _seed_tenant("globex", "g@globex.test", ["directory.view"])
    own = _tenant_skill(acme)
    foreign = _tenant_skill(globex)

    resp = APIClient().post(
        f"/api/skills/{own.id}/edges/",
        {"to_skill": str(foreign.id), "kind": "prerequisite"},
        format="json",
        **_auth(acme, "a@acme.test"),
    )

    assert resp.status_code == 400, resp.json()
    assert "Unknown skill." in str(resp.json())
    assert not SkillEdge.objects.filter(from_skill=own).exists()
