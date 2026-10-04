"""
Job profiles & readiness models (Phase 2).

Tables (see docs/specs/data-model.md and docs/specs/phase-2.md):
- Track              — e.g. Backend, Design, Sales (tenant-scoped).
- JobProfile         — track + grade + title; versioned/publishable (tenant-scoped).
- ProfileRequirement — required skill level per profile; core|supporting|optional (tenant-scoped).
- ReadinessSnapshot  — cached met/total + blocking skills per membership/profile (tenant-scoped).

Readiness is computed (count verified assertions meeting each requirement),
never asserted. All rows inherit ``core.models.TenantScopedModel``.
"""

from __future__ import annotations

from django.contrib.postgres.fields import ArrayField
from django.db import models

from core.models import TenantScopedModel


class Track(TenantScopedModel):
    """A career track (e.g. Backend, Design, Sales)."""

    name = models.CharField(max_length=255)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class JobProfile(TenantScopedModel):
    """
    A grade-level role description within a track.

    Versioned (never mutated in place): editing a published profile creates a new
    ``version`` row with ``status="draft"``; the prior version is retained so
    mid-roadmap learners stay on their snapshot's version.
    """

    STATUS_CHOICES = [
        ("draft", "draft"),
        ("published", "published"),
        ("retired", "retired"),
    ]

    track = models.ForeignKey(Track, on_delete=models.PROTECT, related_name="job_profiles")
    grade = models.SmallIntegerField()
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")
    version = models.SmallIntegerField(default=1)

    class Meta:
        ordering = ["track", "grade", "version"]

    def __str__(self) -> str:
        return f"{self.title} (v{self.version})"


class ProfileRequirement(TenantScopedModel):
    """
    A required skill level within a job profile.

    ``criticality`` determines how the requirement affects readiness: ``core``
    requirements gate promotion (counted in met/total); ``supporting`` and
    ``optional`` are advisory only.

    Each (job_profile, skill) pair is unique — a skill appears only once per profile.
    """

    CRITICALITY_CHOICES = [
        ("core", "core"),
        ("supporting", "supporting"),
        ("optional", "optional"),
    ]

    job_profile = models.ForeignKey(
        JobProfile, on_delete=models.CASCADE, related_name="requirements"
    )
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    min_level = models.SmallIntegerField()
    criticality = models.CharField(max_length=16, choices=CRITICALITY_CHOICES)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["job_profile", "skill"], name="uniq_profile_requirement_profile_skill"
            )
        ]

    def __str__(self) -> str:
        return f"ProfileRequirement({self.job_profile_id}, {self.skill_id}, {self.criticality})"


class ReadinessSnapshot(TenantScopedModel):
    """
    Cached readiness result for a membership against a job profile.

    ``met``/``total`` count only **core** requirements; ``blocking_skill_ids``
    lists unmet core skill UUIDs. Supporting/optional requirements are computed
    but not counted here. ``job_profile_version`` pins the version this snapshot
    was computed against.

    Recomputed synchronously on any ``SkillAssertion`` write for that member, and
    via the ``recompute_readiness`` management command.
    """

    membership = models.ForeignKey(
        "identity.Membership", on_delete=models.CASCADE, related_name="readiness_snapshots"
    )
    job_profile = models.ForeignKey(
        JobProfile, on_delete=models.PROTECT, related_name="readiness_snapshots"
    )
    met = models.SmallIntegerField(default=0)
    total = models.SmallIntegerField(default=0)
    blocking_skill_ids = ArrayField(models.UUIDField(), default=list, blank=True)
    job_profile_version = models.SmallIntegerField()
    computed_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "job_profile"],
                name="uniq_readiness_snapshot_membership_profile",
            )
        ]

    @property
    def readiness_pct(self) -> int:
        """Core requirements met, as a whole percentage (0 when there are none)."""
        return int(self.met * 100 / self.total) if self.total else 0

    def __str__(self) -> str:
        return f"ReadinessSnapshot({self.membership_id}, {self.job_profile_id}, {self.met}/{self.total})"
