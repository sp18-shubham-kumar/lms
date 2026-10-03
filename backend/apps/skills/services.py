"""
Skills service layer.

Thin views call these; business rules (retire, versioning, cycle checks) live here.
See docs/specs/data-model.md and the complete-backend design doc.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.skills.models import (
    SelfDeclaredSkill,
    Skill,
    SkillAssertion,
    SkillEdge,
    SkillLevel,
    TenantSkillOverride,
)
from core import audit

logger = logging.getLogger(__name__)

# Only drafts are editable in place; published/retired rows are pinned by assertions
# and requirements, so changing them means cutting a new version.
EDITABLE_STATUS = "draft"


def retire_skill(skill: Skill, actor: Any) -> Skill:
    """
    Retire a skill: set ``status="retired"`` (never delete — assertions point at it).

    Audited. The caller is responsible for capability gating and tenant scoping.
    """
    skill.status = "retired"
    skill.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=actor,
        action="skill.retire",
        resource=skill,
        tenant_id=skill.tenant_id,
        skill_id=str(skill.id),
    )
    return skill


def publish_skill(skill: Skill, actor: Any) -> Skill:
    """
    Transition a draft skill to ``published``. Audited. Idempotent in effect (a skill
    already published stays published). Caller handles capability gating + scoping.
    """
    skill.status = "published"
    skill.save(update_fields=["status", "updated_at"])
    audit.record(
        actor=actor,
        action="skill.publish",
        resource=skill,
        tenant_id=skill.tenant_id,
        skill_id=str(skill.id),
    )
    return skill


def new_version_from(skill: Skill, actor: Any) -> Skill:
    """
    Create and return a new **draft** version of a published skill.

    The prior version row is retained immutable (assertions/requirements pin the exact
    version they judged). The new draft copies the definition and the rubric grid; its
    ``version`` is the next integer for that (tenant, slug). Audited.
    """
    with transaction.atomic():
        next_version = (
            Skill.objects.filter(tenant_id=skill.tenant_id, slug=skill.slug)
            .order_by("-version")
            .values_list("version", flat=True)
            .first()
            or skill.version
        ) + 1
        new_skill = Skill.objects.create(
            tenant_id=skill.tenant_id,
            domain=skill.domain,
            name=skill.name,
            slug=skill.slug,
            external_code=skill.external_code,
            description=skill.description,
            status="draft",
            version=next_version,
        )
        # Copy the rubric grid onto the new version (prior levels stay with the old row).
        for level in SkillLevel.objects.filter(skill=skill):
            SkillLevel.objects.create(
                skill=new_skill,
                level=level.level,
                title=level.title,
                indicators=list(level.indicators),
                evidence_kinds=list(level.evidence_kinds),
                min_verifier_level=level.min_verifier_level,
                validity_months=level.validity_months,
            )
    audit.record(
        actor=actor,
        action="skill.new_version",
        resource=new_skill,
        tenant_id=new_skill.tenant_id,
        skill_id=str(new_skill.id),
        from_skill_id=str(skill.id),
        version=next_version,
    )
    return new_skill


def ensure_editable(skill: Skill) -> None:
    """
    Reject an in-place edit of a non-draft skill. Raises
    :class:`django.core.exceptions.ValidationError`; callers map it to a 400.
    """
    if skill.status != EDITABLE_STATUS:
        raise ValidationError(f"This skill is {skill.status}; create a new version to change it.")


def versions_of(skill: Skill) -> Any:
    """Every version row sharing the skill's (tenant, slug), newest first."""
    return Skill.objects.filter(tenant_id=skill.tenant_id, slug=skill.slug).order_by("-version")


def would_create_cycle(from_id: Any, to_id: Any) -> bool:
    """
    Return True if adding a ``prerequisite`` edge ``from_id -> to_id`` would close a
    cycle over the prerequisite graph.

    A self-edge is a trivial cycle. Otherwise a cycle forms iff ``from_id`` is already
    reachable from ``to_id`` via prerequisite edges (DFS). ``A -prerequisite-> B`` means
    "A requires B"; a cycle makes the dependency graph unsatisfiable.
    """
    if from_id == to_id:
        return True

    # Adjacency over prerequisite edges only.
    edges = SkillEdge.objects.filter(kind="prerequisite").values_list(
        "from_skill_id", "to_skill_id"
    )
    adjacency: dict[Any, list[Any]] = {}
    for src, dst in edges:
        adjacency.setdefault(src, []).append(dst)

    # Can we reach from_id starting at to_id (following existing prerequisite edges)?
    stack = [to_id]
    seen = set()
    while stack:
        node = stack.pop()
        if node == from_id:
            return True
        if node in seen:
            continue
        seen.add(node)
        stack.extend(adjacency.get(node, []))
    return False


def add_edge(from_skill: Skill, to_skill: Skill, kind: str) -> SkillEdge:
    """
    Create a :class:`SkillEdge`, rejecting a self-edge or (for ``prerequisite``) any
    edge that would introduce a cycle. Raises
    :class:`django.core.exceptions.ValidationError` on rejection.
    """
    if from_skill.id == to_skill.id:
        raise ValidationError("A skill cannot be its own prerequisite/adjacent edge.")
    if kind == "prerequisite" and would_create_cycle(from_skill.id, to_skill.id):
        raise ValidationError("This prerequisite edge would create a cycle.")
    return SkillEdge.objects.create(
        tenant_id=from_skill.tenant_id, from_skill=from_skill, to_skill=to_skill, kind=kind
    )


def _overrides_for(tenant_id: Any, skill_ids: Any) -> dict[Any, TenantSkillOverride]:
    if tenant_id is None:
        return {}
    return {
        ov.skill_id: ov for ov in TenantSkillOverride.objects.filter(skill_id__in=list(skill_ids))
    }


def apply_override(skill: Skill, override: TenantSkillOverride | None) -> Skill:
    """
    Return the skill with the tenant's override applied **in memory** (copy-on-write).

    The global/shared row is never mutated — only the in-memory instance's ``name``
    / ``status`` are overlaid when the override sets them.
    """
    if override is None:
        return skill
    if override.name:
        skill.name = override.name
    if override.status:
        skill.status = override.status
    return skill


def resolve_skill_view(queryset: Any, tenant_id: Any) -> list[Skill]:
    """
    Materialise ``queryset`` applying this tenant's :class:`TenantSkillOverride` rows:
    rename (``name``), relabel (``status``), and drop ``hidden`` skills — all without
    mutating the underlying (possibly global) rows. Overrides from other tenants are
    invisible (the override read is tenant-scoped).
    """
    skills = list(queryset)
    overrides = _overrides_for(tenant_id, [s.id for s in skills])
    resolved: list[Skill] = []
    for skill in skills:
        override = overrides.get(skill.id)
        if override is not None and override.hidden:
            continue
        resolved.append(apply_override(skill, override))
    return resolved


def effective_skill_names(tenant_id: Any, skills: Any) -> dict[Any, str]:
    """This tenant's display name for each skill (override applied), keyed by skill id."""
    skills = list(skills)
    overrides = _overrides_for(tenant_id, [s.id for s in skills])
    return {s.id: (getattr(overrides.get(s.id), "name", "") or s.name) for s in skills}


def record_assertion(
    *,
    membership: Any,
    skill: Skill,
    level: int,
    actor: Any,
    tenant_id: Any,
    note: str = "",
    skill_level: SkillLevel | None = None,
) -> SkillAssertion:
    """
    Record a verified assertion, pinning the skill's current version, then recompute
    the member's readiness (the verified tier is the only readiness input). Audited.
    """
    assertion = SkillAssertion.objects.create(
        tenant_id=tenant_id,
        membership=membership,
        skill=skill,
        level=level,
        skill_level=skill_level,
        skill_version=skill.version,  # pin the version judged
        verified_by=actor,
        verified_at=timezone.now(),
        note=note,
    )
    audit.record(
        actor=actor,
        action="skill.assertion.record",
        resource=assertion,
        tenant_id=tenant_id,
        skill_id=str(skill.id),
        level=assertion.level,
    )
    try:
        from apps.profiles.services import recompute_for_membership

        # Savepoint: a database error here must not poison a caller's open
        # transaction (verify_claim), or "non-fatal" would still fail the request.
        with transaction.atomic():
            recompute_for_membership(assertion.membership)
    except Exception:  # noqa: BLE001
        # Non-fatal: readiness recompute failure must not break the assertion write.
        logger.exception("readiness recompute failed after assertion write")
    return assertion


def _lock_for_review(claim: SelfDeclaredSkill, actor: Any) -> SelfDeclaredSkill:
    """
    Re-read the claim under a row lock and check it is still reviewable. Call inside
    a transaction: concurrent reviewers serialize here, so only one can close it.
    """
    locked = (
        SelfDeclaredSkill.all_tenants.select_for_update(of=("self",))
        .select_related("membership__person", "skill")
        .get(pk=claim.pk)
    )
    _ensure_reviewable(locked, actor)
    return locked


def _ensure_reviewable(claim: SelfDeclaredSkill, actor: Any) -> None:
    if claim.review_status != SelfDeclaredSkill.ReviewStatus.PENDING:
        raise ValidationError(f"This claim is already {claim.review_status}.")
    if claim.membership.person_id == getattr(actor, "pk", None):
        raise PermissionDenied("You cannot review your own skill claim.")


def _mark_reviewed(claim: SelfDeclaredSkill, status: str, actor: Any, note: str) -> None:
    claim.review_status = status
    claim.reviewed_by = actor
    claim.reviewed_at = timezone.now()
    claim.review_note = note
    claim.save(
        update_fields=["review_status", "reviewed_by", "reviewed_at", "review_note", "updated_at"]
    )


def verify_claim(
    claim: SelfDeclaredSkill, *, level: int, actor: Any, note: str = ""
) -> SkillAssertion:
    """
    Verify a pending claim at ``level`` (which may differ from the claimed level):
    records the assertion and closes the claim. Self-review is refused.
    """
    with transaction.atomic():
        claim = _lock_for_review(claim, actor)
        assertion = record_assertion(
            membership=claim.membership,
            skill=claim.skill,
            level=level,
            actor=actor,
            tenant_id=claim.tenant_id,
            note=note,
        )
        _mark_reviewed(claim, SelfDeclaredSkill.ReviewStatus.VERIFIED, actor, note)
    return assertion


def reject_claim(claim: SelfDeclaredSkill, *, actor: Any, note: str) -> SelfDeclaredSkill:
    """Reject a pending claim with a reason. No assertion is recorded. Audited."""
    with transaction.atomic():
        claim = _lock_for_review(claim, actor)
        _mark_reviewed(claim, SelfDeclaredSkill.ReviewStatus.REJECTED, actor, note)
        audit.record(
            actor=actor,
            action="skill.claim.reject",
            resource=claim,
            tenant_id=claim.tenant_id,
            skill_id=str(claim.skill_id),
        )
    return claim
