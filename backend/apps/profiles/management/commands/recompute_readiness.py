"""
Management command: recompute_readiness

Recomputes ReadinessSnapshot for all membership+job_profile combinations in scope.
Optionally restricted to a single tenant via --tenant <slug>.

Usage:
    manage.py recompute_readiness
    manage.py recompute_readiness --tenant acme
"""

from __future__ import annotations

from argparse import ArgumentParser

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Recompute readiness snapshots for all memberships (optionally filtered by tenant)."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--tenant",
            dest="tenant_slug",
            default=None,
            help="Restrict recomputation to a single tenant (by slug).",
        )

    def handle(self, *args: object, **options: object) -> None:
        from apps.identity.models import Membership, Tenant
        from apps.profiles import services
        from apps.profiles.models import JobProfile

        tenant_slug = options.get("tenant_slug")

        if tenant_slug:
            try:
                tenant = Tenant.objects.get(slug=tenant_slug)
            except Tenant.DoesNotExist as exc:
                raise CommandError(f"Tenant with slug '{tenant_slug}' not found.") from exc
            tenants = [tenant]
        else:
            tenants = list(Tenant.objects.all())

        total_recomputed = 0
        for tenant in tenants:
            memberships = list(Membership.all_tenants.filter(tenant=tenant, status="active"))
            profiles = list(JobProfile.all_tenants.filter(tenant=tenant))
            if not profiles:
                continue
            for membership in memberships:
                for profile in profiles:
                    services.compute_readiness(membership, profile)
                    total_recomputed += 1

        self.stdout.write(
            self.style.SUCCESS(f"Recomputed {total_recomputed} readiness snapshot(s).")
        )
