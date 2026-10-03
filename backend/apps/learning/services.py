"""
Learning service layer — progress transitions and gap-based recommendations.

Progress is self-reported. Nothing here writes ``SkillAssertion`` or touches
readiness snapshots: finishing a course does not verify a skill.

Functions:
- start_progress(membership, resource, actor) -> (LearningProgress, created)
- update_progress(progress, actor, completed_modules=None, status=None) -> LearningProgress
- recommend_for_gaps(membership, job_profile) -> list[dict]
"""

from __future__ import annotations

from functools import partial
from typing import Any

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.learning.models import LearningProgress, LearningResource, ResourceSkill
from core import audit


def _require_published(resource: LearningResource) -> None:
    if resource.status != "published":
        raise ValidationError({"resource": "This resource is not available."})


def _record(actor: Any, action: str, progress: LearningProgress) -> None:
    audit.record(
        actor=actor,
        action=action,
        resource=progress,
        tenant_id=progress.tenant_id,
        resource_id=str(progress.resource_id),
        status=progress.status,
        completed_modules=progress.completed_modules,
    )


@transaction.atomic
def start_progress(
    membership: Any, resource: LearningResource, actor: Any
) -> tuple[LearningProgress, bool]:
    """
    Start a resource. Idempotent: an existing row is returned unchanged, except a
    ``not_started`` row, which moves to ``in_progress``.
    """
    _require_published(resource)
    progress, created = LearningProgress.objects.get_or_create(
        membership=membership,
        resource=resource,
        defaults={"tenant_id": membership.tenant_id},
    )
    if progress.status == "not_started":
        progress.status = "in_progress"
        progress.started_at = timezone.now()
        progress.save(update_fields=["status", "started_at", "updated_at"])
        _record(actor, "learning.progress.start", progress)
    return progress, created


@transaction.atomic
def update_progress(
    progress: LearningProgress,
    actor: Any,
    *,
    completed_modules: int | None = None,
    status: str | None = None,
) -> LearningProgress:
    """
    Apply a learner's progress update.

    - ``status="not_started"`` resets the row (modules 0, timestamps cleared).
    - ``status="completed"`` or reaching ``module_count`` modules completes it.
    - Anything else is ``in_progress``. Re-opening a completed resource keeps it
      one module short of the end so it isn't immediately complete again.

    Resetting is always allowed; advancing requires a published resource.
    """
    resource = progress.resource
    total = resource.module_count
    now = timezone.now()

    if status == "not_started":
        progress.status = "not_started"
        progress.completed_modules = 0
        progress.started_at = None
        progress.completed_at = None
        action = "learning.progress.reset"
    else:
        _require_published(resource)
        modules = progress.completed_modules if completed_modules is None else completed_modules
        if modules > total:
            raise ValidationError({"completed_modules": f"This resource has {total} module(s)."})
        if status == "completed" or (status is None and modules == total):
            progress.status = "completed"
            progress.completed_modules = total
            progress.completed_at = progress.completed_at or now
            action = "learning.progress.complete"
        else:
            progress.status = "in_progress"
            progress.completed_modules = min(modules, total - 1)
            progress.completed_at = None
            action = "learning.progress.update"
        progress.started_at = progress.started_at or now

    progress.save()
    _record(actor, action, progress)
    return progress


def _rank(
    link: ResourceSkill, req: Any, progress_by_resource: dict[Any, LearningProgress]
) -> tuple[bool, bool, int]:
    """Not-yet-completed first, then in-gap before overshoot, then lowest level."""
    progress = progress_by_resource.get(link.resource_id)
    done = progress is not None and progress.status == "completed"
    return (done, link.level > req.min_level, link.level)


def _recommended(link: Any, progress_by_resource: dict[Any, Any]) -> dict[str, Any]:
    return {
        "resource": link.resource,
        "target_level": link.level,
        "progress": progress_by_resource.get(link.resource_id),
    }


def recommend_for_gaps(membership: Any, job_profile: Any) -> list[dict[str, Any]]:
    """
    For every requirement the learner hasn't met, list the published resources that
    teach that skill beyond their current verified level.

    Gaps come back in the order the learner gap view uses (smallest gap first).
    Within a gap, resources inside the gap come first (lowest target level = the
    next step), then resources that overshoot the requirement; completed resources
    go last.

    Resources that teach the skill only up to the learner's current level don't
    close the gap, so they are kept apart as ``refreshers`` (highest level first)
    rather than dropped: the learner can still see that the library covers the
    skill, just not far enough.
    """
    from apps.profiles.models import ProfileRequirement
    from apps.profiles.services import best_verified_levels

    current = best_verified_levels(membership)
    unmet = [
        req
        for req in ProfileRequirement.objects.filter(job_profile=job_profile).select_related(
            "skill"
        )
        if current.get(req.skill_id, 0) < req.min_level
    ]
    unmet.sort(key=lambda req: (req.min_level - current.get(req.skill_id, 0), req.skill.name))

    skill_ids = [req.skill_id for req in unmet]
    links = list(
        ResourceSkill.objects.filter(skill_id__in=skill_ids, resource__status="published")
        .select_related("resource")
        .order_by("level", "resource__title")
    )
    progress_by_resource = {
        p.resource_id: p
        for p in LearningProgress.objects.filter(
            membership=membership, resource_id__in={link.resource_id for link in links}
        )
    }

    gaps = []
    for req in unmet:
        level_now = current.get(req.skill_id, 0)
        skill_links = [link for link in links if link.skill_id == req.skill_id]
        candidates = [link for link in skill_links if link.level > level_now]
        refreshers = [link for link in skill_links if link.level <= level_now]

        candidates.sort(key=partial(_rank, req=req, progress_by_resource=progress_by_resource))
        refreshers.sort(key=lambda link: (-link.level, link.resource.title))
        gaps.append(
            {
                "skill_id": req.skill_id,
                "skill_name": req.skill.name,
                "criticality": req.criticality,
                "min_level": req.min_level,
                "current_level": current.get(req.skill_id),
                "resources": [_recommended(link, progress_by_resource) for link in candidates],
                "refreshers": [_recommended(link, progress_by_resource) for link in refreshers],
            }
        )
    return gaps
