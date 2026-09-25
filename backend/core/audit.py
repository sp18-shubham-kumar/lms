"""
Append-only audit log helper.

The spec requires an append-only audit trail and a nightly cross-tenant leak
scan. Every state-changing action should call :func:`record` with the actor,
the action key, and the affected resource.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("audit")


def record(
    *,
    actor: Any,
    action: str,
    resource: Any | None = None,
    tenant_id: Any | None = None,
    **metadata: Any,
) -> None:
    """
    Record an audit event by inserting a row into the append-only ``AuditLog``
    table (never update or delete). Also emits a structured log line for
    observability.
    """
    from core.models import AuditLog  # lazy import: avoids app-loading cycle

    actor_obj = actor if getattr(actor, "pk", None) is not None else None
    AuditLog.objects.create(
        tenant_id=tenant_id,
        actor=actor_obj,
        action=action,
        resource_type=type(resource).__name__ if resource is not None else "",
        resource_id=getattr(resource, "id", None),
        metadata=metadata,
    )
    logger.info("audit", extra={"action": action, "tenant_id": tenant_id})
