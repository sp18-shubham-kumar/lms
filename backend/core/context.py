"""
Ambient tenant context.

The active tenant id is stored in a ``ContextVar`` for the duration of a request
(set by :class:`core.middleware.TenantContextMiddleware`) or a background job
(set explicitly by the worker). Everything that reads tenant-scoped data goes
through here, so a forgotten filter fails closed rather than leaking across
tenants.

Usage
-----
>>> from core.context import set_current_tenant, get_current_tenant
>>> token = set_current_tenant(tenant_id)
>>> get_current_tenant()
UUID(...)
>>> reset_current_tenant(token)
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from contextvars import ContextVar, Token
from uuid import UUID

_current_tenant: ContextVar[UUID | None] = ContextVar("current_tenant", default=None)


def set_current_tenant(tenant_id: UUID | None) -> Token:
    """Set the active tenant and return a token for later reset."""
    return _current_tenant.set(tenant_id)


def get_current_tenant() -> UUID | None:
    """Return the active tenant id, or ``None`` if no tenant is in context."""
    return _current_tenant.get()


def reset_current_tenant(token: Token) -> None:
    """Restore the previous tenant context."""
    _current_tenant.reset(token)


@contextlib.contextmanager
def tenant_context(tenant_id: UUID | None) -> Iterator[None]:
    """Scope a block of code to a tenant (handy in jobs and tests)."""
    token = set_current_tenant(tenant_id)
    try:
        yield
    finally:
        reset_current_tenant(token)
