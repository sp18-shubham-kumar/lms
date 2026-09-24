# Backend guide (Django + DRF)

Python 3.11 · Django 5.1 · DRF · SimpleJWT · Postgres. Virtualenv at `backend/.venv`.

## Layout

```
config/
  settings/{base,dev,test,prod}.py   split settings; env via django-environ (.env)
  urls.py                            /api/ root; domain routers added as implemented
core/                                shared infra — inherit from here, don't reinvent
  models.py       UUIDModel, TimeStampedModel, TenantScopedModel (abstract bases)
  managers.py     TenantScopedManager / TenantScopedQuerySet (fail-closed scoping)
  context.py      get/set_current_tenant, tenant_context() — the ambient tenant
  middleware.py   TenantContextMiddleware (resolves tenant per request)
  permissions.py  can(actor, capability, resource) + HasCapability DRF permission
  audit.py        record(...) append-only audit seam
  pagination.py, exceptions.py
  tests/          smoke + tenant isolation harness
apps/
  identity/  authz/  skills/  profiles/   domain apps (empty stubs, docstrings point to specs)
```

## Commands

```bash
cd backend
.venv/bin/python manage.py runserver        # or: make backend
.venv/bin/python manage.py makemigrations
.venv/bin/python manage.py migrate          # needs Postgres: make db-up
.venv/bin/pytest                            # or: make test-backend
.venv/bin/ruff check . && .venv/bin/black . && .venv/bin/mypy .   # or: make lint-backend
```

Settings module defaults: `manage.py`/dev → `config.settings.dev`; pytest →
`config.settings.test` (see `pyproject.toml`); wsgi/prod → `config.settings.prod`.

## How to add a domain model (the checklist)

1. Inherit **`core.models.TenantScopedModel`** (gives UUID id, timestamps, `tenant` FK,
   scoped `objects` manager, and `all_tenants` escape hatch). `Person`/`Tenant` are the
   only non-scoped models.
2. Field names should match `docs/specs/data-model.md` exactly.
3. `makemigrations` — review the migration; keep them additive/online where possible.
4. Serializer in `serializers.py`, ViewSet in `views.py`, register a route in the app's
   `urls.py`, then uncomment the app's `include(...)` in `config/urls.py`.
5. Gate the view: set `required_capability` and add `HasCapability` to
   `permission_classes` (deny by default is already the global default).
6. Register in `admin.py` if useful for demos.
7. **Write an isolation test**: seed two tenants, hit the list endpoint as tenant A,
   assert none of tenant B's rows appear. Extend `core/tests/test_tenant_isolation.py`
   (there's a helper stub `assert_list_is_tenant_isolated`).
8. Call `core.audit.record(...)` on any state-changing action.

## Conventions

- One decision path for authz: `can()`. Don't scatter permission logic in views.
- Cross-module data access goes through the owning app's service layer, not raw joins.
- Every write endpoint should accept an idempotency key (clients retry).
- Background jobs must set tenant context explicitly (`tenant_context(...)`); no tenant → fail.
- Keep `ruff` + `black` + `mypy` clean. Known false positives are suppressed with a
  targeted `# noqa` / `# type: ignore[...]` and a comment — do the same, don't broaden config.
