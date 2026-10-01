from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
from apps.identity.models import Membership, Person, Tenant
from apps.skills.models import Skill, SkillDomain
from core.context import tenant_context

CAPABILITIES = [
    "directory.view",
    "skill.claim.submit",
    "skill.verify",
    "verifier.grant",
    "member.invite",
    "member.offboard",
    "credential.revoke",
    "taxonomy.edit",
    "jobprofile.edit",
    "report.org.view",
]
# The capabilities Part A/B endpoints gate on (reconciled below; superset is fine).
REQUIRED_CAPABILITIES = [
    "directory.view",
    "skill.claim.submit",
    "taxonomy.edit",
    "jobprofile.edit",
    "member.invite",
    "member.offboard",
    "skill.verify",
    "report.org.view",
]
ROLE_CAPS: dict[str, list[str]] = {
    "Learner": ["directory.view", "skill.claim.submit"],
    "Manager": [
        "directory.view",
        "skill.claim.submit",
        "report.org.view",
        "skill.verify",
    ],
    "Admin": CAPABILITIES,
}

# A few global (tenant NULL) skill domains + skills, read-only and shared by all tenants.
GLOBAL_DOMAINS: dict[str, list[tuple[str, str]]] = {
    "Data": [("SQL", "sql"), ("Python", "python"), ("Data modeling", "data-modeling")],
    "Platform": [("Airflow", "airflow"), ("dbt", "dbt"), ("Kafka", "kafka")],
}


class Command(BaseCommand):
    help = "Seed two demo tenants with roles, capabilities, people and memberships."

    def handle(self, *args: object, **options: object) -> None:
        # Reconcile every capability the endpoints gate on (plus the legacy superset).
        for key in [*CAPABILITIES, *REQUIRED_CAPABILITIES]:
            Capability.objects.get_or_create(key=key)

        self._global_skills()

        acme = self._tenant("acme", "Acme", "#4f46e5")
        northwind = self._tenant("northwind", "Northwind", "#0891b2")

        alice = self._person("alice@acme.test", "Alice Admin")
        bob = self._person("bob@acme.test", "Bob Learner")
        dana = self._person("dana@shared.test", "Dana Dual")

        self._member(acme, alice, "Admin")
        self._member(acme, bob, "Learner")
        self._member(acme, dana, "Learner")
        self._member(northwind, dana, "Manager")

        self.stdout.write(self.style.SUCCESS("seed_demo complete."))

    def _global_skills(self) -> None:
        # Globals (tenant NULL) use the unscoped default manager; no tenant context needed.
        for domain_name, skills in GLOBAL_DOMAINS.items():
            domain, _ = SkillDomain.objects.get_or_create(tenant=None, name=domain_name)
            for skill_name, slug in skills:
                Skill.objects.get_or_create(
                    tenant=None,
                    slug=slug,
                    version=1,
                    defaults={
                        "domain": domain,
                        "name": skill_name,
                        "status": "published",
                    },
                )

    def _tenant(self, slug: str, name: str, accent: str) -> Tenant:
        tenant, _ = Tenant.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "status": "active", "plan": "pro", "accent_color": accent},
        )
        with tenant_context(tenant.id):
            for role_name, caps in ROLE_CAPS.items():
                role, _ = Role.objects.get_or_create(
                    tenant=tenant, name=role_name, defaults={"is_system": True}
                )
                for key in caps:
                    RoleCapability.objects.get_or_create(
                        tenant=tenant, role=role, capability_id=key
                    )
        return tenant

    def _person(self, email: str, name: str) -> Person:
        UserModel = get_user_model()
        person = UserModel.objects.filter(email=email).first()
        if person is None:
            person = UserModel.objects.create_user(
                email=email, display_name=name, password="demo-pass-123"
            )
        return person

    def _member(self, tenant: Tenant, person: Person, role_name: str) -> None:
        with tenant_context(tenant.id):
            Membership.objects.get_or_create(
                person=person, tenant=tenant, defaults={"status": "active"}
            )
            role = Role.objects.get(tenant=tenant, name=role_name)
            RoleGrant.objects.get_or_create(
                tenant=tenant,
                principal_type="person",
                principal_id=person.id,
                role=role,
            )
