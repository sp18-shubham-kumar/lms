"""
Skills service layer.

Thin views call these; business rules (retire, versioning, cycle checks) live here.
See docs/specs/data-model.md and the complete-backend design doc.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.skills.models import Skill, SkillEdge, TenantSkillOverride
from core import audit


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
