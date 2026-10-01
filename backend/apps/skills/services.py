"""
Skills service layer.

Thin views call these; business rules (retire, versioning, cycle checks) live here.
See docs/specs/data-model.md and the complete-backend design doc.
"""

from __future__ import annotations

from typing import Any

from apps.skills.models import Skill
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
