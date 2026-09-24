"""
Append-only audit log helper (skeleton).

The spec requires an append-only audit trail and a nightly cross-tenant leak
scan. Phase 1 will add a concrete ``AuditLog`` model; this seam lets call sites
record events now so wiring the model later is a drop-in change.

Every state-changing action should call :func:`record` with the actor, the
action key, and the affected resource.
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
    Record an audit event.

    Currently logs to the ``audit`` logger. Phase 1 replaces the body with an
    insert into the append-only ``AuditLog`` table (never an update or delete).
    """
    logger.info(
        "audit",
        extra={
            "actor": getattr(actor, "id", actor),
            "action": action,
            "resource": getattr(resource, "id", resource),
            "tenant_id": tenant_id,
            "metadata": metadata,
        },
    )
