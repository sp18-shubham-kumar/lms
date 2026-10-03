from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.authz.models import Capability, Role, RoleCapability, RoleGrant
from apps.identity.models import Membership, OrgUnit, Person, Tenant
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
    "resource.edit",
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

# SkillLevel definitions: skill_slug -> list of (level, title)
SKILL_LEVELS: dict[str, list[tuple[int, str]]] = {
    "sql": [
        (1, "SQL Basics"),
        (2, "SQL Intermediate"),
        (3, "SQL Advanced"),
    ],
    "python": [
        (1, "Python Basics"),
        (2, "Python Intermediate"),
        (3, "Python Advanced"),
    ],
    "data-modeling": [
        (1, "Data Modeling Basics"),
        (2, "Data Modeling Intermediate"),
        (3, "Data Modeling Advanced"),
    ],
    "dbt": [
        (1, "dbt Basics"),
        (2, "dbt Intermediate"),
        (3, "dbt Advanced"),
    ],
    "kafka": [
        (1, "Kafka Basics"),
        (2, "Kafka Intermediate"),
    ],
    "airflow": [
        (1, "Airflow Basics"),
        (2, "Airflow Intermediate"),
    ],
}

# Data Engineer job profiles: title, grade, list of (skill_slug, min_level, criticality)
DATA_ENGINEER_PROFILES: list[tuple[str, int, list[tuple[str, int, str]]]] = [
    (
        "Data Engineer L1",
        1,
        [
            ("sql", 1, "core"),
            ("python", 1, "core"),
            ("data-modeling", 1, "supporting"),
        ],
    ),
    (
        "Data Engineer L2",
        2,
        [
            ("sql", 2, "core"),
            ("python", 2, "core"),
            ("data-modeling", 2, "core"),
            ("dbt", 1, "supporting"),
            ("kafka", 1, "optional"),
        ],
    ),
    (
        "Data Engineer L3",
        3,
        [
            ("sql", 3, "core"),
            ("python", 3, "core"),
            ("data-modeling", 3, "core"),
            ("dbt", 2, "core"),
            ("kafka", 2, "supporting"),
            ("airflow", 1, "optional"),
        ],
    ),
]

# Acme's resource library: (title, kind, provider, url, modules, minutes, [(skill_slug, level)])
LEARNING_RESOURCES: list[tuple[str, str, str, str, int, int, list[tuple[str, int]]]] = [
    ("Intermediate Python for Data", "course", "Acme Academy", "", 6, 240, [("python", 2)]),
    ("Python Testing and Packaging", "course", "Acme Academy", "", 5, 180, [("python", 3)]),
    (
        "Window Functions in Practice",
        "article",
        "Mode",
        "https://mode.com/sql-tutorial/sql-window-functions",
        1,
        25,
        [("sql", 3)],
    ),
    (
        "dbt Fundamentals",
        "course",
        "dbt Labs",
        "https://learn.getdbt.com/courses/dbt-fundamentals",
        5,
        300,
        [("dbt", 1), ("sql", 2)],
    ),
    ("The Data Warehouse Toolkit", "book", "Kimball", "", 12, 900, [("data-modeling", 3)]),
    ("Kafka in 30 Minutes", "video", "Confluent", "", 1, 30, [("kafka", 1)]),
]

# Bob's self-reported progress: (resource title, completed modules)
BOB_PROGRESS: list[tuple[str, int]] = [("Intermediate Python for Data", 2)]

# Bob's verified assertions: (skill_slug, level)
BOB_ASSERTIONS: list[tuple[str, int]] = [
    ("sql", 2),
    ("python", 1),
    ("data-modeling", 2),
]


class Command(BaseCommand):
    help = "Seed two demo tenants with roles, capabilities, people and memberships."

    def handle(self, *args: object, **options: object) -> None:
        # Reconcile every capability the endpoints gate on (plus the legacy superset).
        for key in [*CAPABILITIES, *REQUIRED_CAPABILITIES]:
            Capability.objects.get_or_create(key=key)

        self._global_skills()
        self._global_skill_levels()

        acme = self._tenant("acme", "Acme", "#4f46e5")
        northwind = self._tenant("northwind", "Northwind", "#0891b2")

        alice = self._person("alice@acme.test", "Alice Admin")
        bob = self._person("bob@acme.test", "Bob Learner")
        dana = self._person("dana@shared.test", "Dana Dual")

        self._member(acme, alice, "Admin")
        self._member(acme, bob, "Learner")
        self._member(acme, dana, "Learner")
        self._member(northwind, dana, "Manager")

        self._data_engineer_ladder(acme, bob)
        self._seed_org_unit(acme, [alice, bob, dana])
        self._learning_resources(acme, bob)

        self.stdout.write(self.style.SUCCESS("seed_demo complete."))

    def _seed_org_unit(self, tenant: Tenant, people: list[Person]) -> None:
        """
        Put the Acme demo members in one org unit and compute their readiness
        against Data Engineer L2, so the team heatmap has rows to render.
        Idempotent.
        """
        from apps.profiles.models import JobProfile
        from apps.profiles.services import compute_readiness

        with tenant_context(tenant.id):
            unit, _ = OrgUnit.objects.get_or_create(
                tenant=tenant, name="Data Platform", defaults={"path": "data-platform"}
            )
            l2 = JobProfile.objects.filter(track__name="Data Engineering", grade=2).first()
            for person in people:
                membership = Membership.objects.filter(person=person, tenant=tenant).first()
                if membership is None:
                    continue
                if membership.org_unit_id != unit.id:
                    membership.org_unit = unit
                    membership.save(update_fields=["org_unit"])
                if l2 is not None:
                    compute_readiness(membership, l2)

    def _learning_resources(self, tenant: Tenant, bob: Person) -> None:
        """Seed a small resource library linked to the global skills, plus Bob's progress."""
        from django.utils import timezone

        from apps.learning.models import LearningProgress, LearningResource, ResourceSkill

        with tenant_context(tenant.id):
            for title, kind, provider, url, modules, minutes, links in LEARNING_RESOURCES:
                resource, _ = LearningResource.objects.get_or_create(
                    tenant=tenant,
                    title=title,
                    defaults={
                        "kind": kind,
                        "provider": provider,
                        "url": url,
                        "module_count": modules,
                        "duration_minutes": minutes,
                        "status": "published",
                    },
                )
                for skill_slug, level in links:
                    skill = Skill.objects.filter(tenant__isnull=True, slug=skill_slug).first()
                    if skill is not None:
                        ResourceSkill.objects.get_or_create(
                            tenant=tenant, resource=resource, skill=skill, defaults={"level": level}
                        )

            bob_membership = Membership.objects.get(person=bob, tenant=tenant)
            for title, done in BOB_PROGRESS:
                resource = LearningResource.objects.get(title=title)
                LearningProgress.objects.get_or_create(
                    tenant=tenant,
                    membership=bob_membership,
                    resource=resource,
                    defaults={
                        "status": "in_progress",
                        "completed_modules": done,
                        "started_at": timezone.now(),
                    },
                )

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

    def _global_skill_levels(self) -> None:
        """Seed SkillLevel rows for each global skill (idempotent)."""
        from apps.skills.models import SkillLevel

        for slug, levels in SKILL_LEVELS.items():
            skill = Skill.objects.filter(tenant__isnull=True, slug=slug).first()
            if skill is None:
                continue
            for level_num, title in levels:
                SkillLevel.objects.get_or_create(
                    skill=skill,
                    level=level_num,
                    defaults={"title": title},
                )

    def _data_engineer_ladder(self, tenant: Tenant, bob: Person) -> None:
        """
        Seed the Data Engineering track with L1/L2/L3 job profiles, then seed
        verified assertions for bob and compute his readiness snapshot for L2.
        All database writes happen inside tenant context.
        """
        from django.utils import timezone

        from apps.profiles.models import JobProfile, ProfileRequirement, Track
        from apps.profiles.services import compute_readiness, publish_job_profile
        from apps.skills.models import SkillAssertion

        with tenant_context(tenant.id):
            # Create the track.
            track, _ = Track.objects.get_or_create(tenant=tenant, name="Data Engineering")

            # Create job profiles (idempotent by title+grade+version+track).
            profiles = {}
            for title, grade, requirements in DATA_ENGINEER_PROFILES:
                profile, created = JobProfile.objects.get_or_create(
                    tenant=tenant,
                    track=track,
                    grade=grade,
                    title=title,
                    version=1,
                    defaults={"status": "draft"},
                )
                # Add requirements (idempotent by job_profile+skill).
                for skill_slug, min_level, criticality in requirements:
                    skill = Skill.objects.filter(tenant__isnull=True, slug=skill_slug).first()
                    if skill is None:
                        continue
                    ProfileRequirement.objects.get_or_create(
                        tenant=tenant,
                        job_profile=profile,
                        skill=skill,
                        defaults={"min_level": min_level, "criticality": criticality},
                    )
                # Publish if still draft.
                if profile.status == "draft":
                    publish_job_profile(profile, actor=None)
                profiles[grade] = profile

            # Bob's membership.
            bob_membership = Membership.objects.get(person=bob, tenant=tenant)

            # Seed verified assertions for bob.
            for skill_slug, level in BOB_ASSERTIONS:
                skill = Skill.objects.filter(tenant__isnull=True, slug=skill_slug).first()
                if skill is None:
                    continue
                SkillAssertion.all_tenants.get_or_create(
                    membership=bob_membership,
                    skill=skill,
                    defaults={
                        "tenant_id": tenant.id,
                        "level": level,
                        "skill_version": skill.version,
                        "verified_by": None,
                        "verified_at": timezone.now(),
                        "note": "Seeded by seed_demo",
                    },
                )

            # Compute readiness for bob against L2.
            l2_profile = profiles.get(2)
            if l2_profile is not None:
                compute_readiness(bob_membership, l2_profile)

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
