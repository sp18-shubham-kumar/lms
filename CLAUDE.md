# Skills LMS — project guide for Claude

Multi-tenant **Skills LMS**: tracks skills (not courses), permission-based verification,
two-tier confidence (self-claimed vs verified). Built in phases. Read the specs in
`docs/specs/` before implementing — they are the distilled source of truth.

## Repo map

```
backend/    Django + DRF API (Python 3.11, Postgres).  See backend/CLAUDE.md
frontend/   Vite + React + TS SPA.                      See frontend/CLAUDE.md
docs/specs/ Distilled, Claude-readable specs (start here)
docs/*.docx, *.html   Original source docs (authoritative; re-read when unsure)
docker-compose.yml    Local Postgres
ecosystem.config.js   PM2 process defs (runs backend + frontend)
Makefile    One-word dev commands (run `make help`)
```

## The three product commitments (never violate)

1. **Content is not the product** — track skills, not course completions.
2. **Verification is permission-based** — who can confirm what is *data* (`verifier_authority`), not code.
3. **Two-tier confidence** — a self-claim and a verified assertion are *separate records*.
   Reports/promotions/rewards read only the verified tier.

## Hard rules (enforced in review)

- **Every domain table carries `tenant_id`.** Inherit `core.models.TenantScopedModel`.
  No exceptions, including join tables.
- **All reads go through the tenant-scoped manager** (`Model.objects`), which fails
  closed (returns nothing) when no tenant is in context. Use `Model.all_tenants` only
  for provisioning / admin / the isolation scan, never in a request handler.
- **Authorization is deny-by-default**, funnelled through `core.permissions.can(actor,
  capability, resource)`. Every deny is logged with the failing check.
- **Skills are versioned, never mutated in place**; retire, don't delete.
- **State-changing actions are audited** (`core.audit.record`).
- **Frontend caches per tenant** and clears on tenant switch; writes to assertions/ledger
  are pessimistic (explicit confirm), never optimistic.

## Current status

Scaffold only — apps run, tooling/tests are wired, **no domain features implemented yet**.
Domain apps (`identity`, `authz`, `skills`, `profiles`) are registered but empty. Implement
[Phase 1](docs/specs/phase-1.md) then [Phase 2](docs/specs/phase-2.md); build order in
[roadmap.md](docs/specs/roadmap.md).

## Dev commands (see `make help` for all)

```bash
make setup       # venv + backend deps + frontend deps + .env files
make db-up       # start Postgres (docker)
make migrate     # apply migrations
make dev         # Postgres + backend + frontend via PM2
make test        # backend pytest + frontend vitest
make lint        # ruff + black + mypy + oxlint + tsc
```

Backend runs on **:8000**, frontend on **:5173**, Postgres on **:5432**.
If `:8000` is taken, either free it or change the port in `ecosystem.config.js` /
`backend/.env` and the frontend's `VITE_API_URL`.

## Working style

- Follow existing patterns in `core/` and the settings split. When adding a model,
  see the checklist in `backend/CLAUDE.md`.
- Every new tenant-scoped list endpoint gets an isolation test (seed two tenants,
  assert tenant A sees zero of tenant B's rows). Not optional.
- Keep app names aligned 1:1 with the spec module boundaries.
