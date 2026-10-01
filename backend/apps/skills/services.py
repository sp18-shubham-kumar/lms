"""
Skills service layer.

Thin views call these; business rules (retire, versioning, cycle checks) live here.
See docs/specs/data-model.md and the complete-backend design doc.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError

from apps.skills.models import Skill, SkillEdge
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
