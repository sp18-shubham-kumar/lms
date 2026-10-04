"""
Learning resources & progress models.

Tables (see docs/Skills_LMS_Project_Overview_.docx, "Learning Resource" and
"Learning Progress" data areas):
- LearningResource — learning content (course, article, …) owned by a tenant.
- ResourceSkill    — links a resource to a skill and the level it teaches toward.
- LearningProgress — one learner's self-reported progress through one resource.

Progress is the *self-reported* tier, like self-declared skills: it never creates
a verified assertion and never moves readiness (readiness reads only
``SkillAssertion``). All rows inherit ``core.models.TenantScopedModel``.
"""

from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import TenantScopedModel


class LearningResource(TenantScopedModel):
    """A piece of learning content. Archive, don't delete — progress points at it."""

    KIND_CHOICES = [
        ("course", "course"),
        ("article", "article"),
        ("video", "video"),
        ("book", "book"),
        ("other", "other"),
    ]
    STATUS_CHOICES = [
        ("draft", "draft"),
        ("published", "published"),
        ("archived", "archived"),
    ]

    title = models.CharField(max_length=255)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default="course")
    url = models.URLField(max_length=1024, blank=True, default="")
    provider = models.CharField(max_length=255, blank=True, default="")
    description = models.TextField(blank=True, default="")
    module_count = models.PositiveSmallIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(500)]
    )
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="draft")

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class ResourceSkill(TenantScopedModel):
    """A resource teaches ``skill`` up to ``level`` (1..5). One link per skill per resource."""

    resource = models.ForeignKey(
        LearningResource, on_delete=models.CASCADE, related_name="skill_links"
    )
    skill = models.ForeignKey("skills.Skill", on_delete=models.PROTECT, related_name="+")
    level = models.SmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    class Meta:
        ordering = ["level"]
        constraints = [
            models.UniqueConstraint(fields=["resource", "skill"], name="uniq_resource_skill")
        ]

    def __str__(self) -> str:
        return f"ResourceSkill({self.resource_id}, {self.skill_id}, L{self.level})"


class LearningProgress(TenantScopedModel):
    """A learner's self-reported progress through a resource. One row per member per resource."""

    STATUS_CHOICES = [
        ("not_started", "not_started"),
        ("in_progress", "in_progress"),
        ("completed", "completed"),
    ]

    membership = models.ForeignKey(
        "identity.Membership", on_delete=models.CASCADE, related_name="learning_progress"
    )
    resource = models.ForeignKey(
        LearningResource, on_delete=models.PROTECT, related_name="progress"
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="not_started")
    completed_modules = models.PositiveSmallIntegerField(default=0)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "resource"], name="uniq_learning_progress_member_resource"
            )
        ]

    def __str__(self) -> str:
        return f"LearningProgress({self.membership_id}, {self.resource_id}, {self.status})"
