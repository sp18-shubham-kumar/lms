# Skills LMS

A multi-tenant **Skills Learning Management System**. It tracks *skills* (not course
completions), uses permission-based verification, and keeps self-claimed and verified
skills as separate tiers. Built in phases — see [`docs/specs/`](docs/specs/).

- **Backend**: Django + Django REST Framework, Postgres (`backend/`)
- **Frontend**: Vite + React + TypeScript SPA (`frontend/`)
- **Multitenancy**: shared schema, `tenant_id` on every domain row, app-level scoping
- **Auth**: JWT (SimpleJWT)

> Status: **Phase 1 in progress**. The foundation is implemented — tenants, people,
> memberships, roles/capabilities, JWT login, a capability-gated session, and a
> tenant-isolated People directory. See [Phase 1](docs/specs/phase-1.md) for what's next.

## Prerequisites

Python 3.11+, Node 20+, Docker (for Postgres). PM2 is fetched on demand via `npx`.

## Quickstart

```bash
# 1. Install everything (venv, backend deps, frontend deps, .env files)
make setup

# 2. Start Postgres and apply migrations
make db-up
make migrate

# 3. Seed two demo tenants with roles, capabilities, people and memberships
cd backend && .venv/bin/python manage.py seed_demo && cd ..

# 4. Run both apps (backend :8000, frontend :5173) via PM2
make dev
#    ...or run them separately:
#    make backend      # http://localhost:8000
#    make frontend     # http://localhost:5173
```

Then open:
- Frontend — http://localhost:5173
- API health — http://localhost:8000/api/health/
- API docs (Swagger) — http://localhost:8000/api/schema/swagger-ui/

Stop PM2 apps with `make stop`; stop Postgres with `make db-down`.

### Demo login

`seed_demo` creates two tenants (**Acme**, **Northwind**) and these accounts — password
`demo-pass-123` for all:

| Email | Tenant(s) | Role | What you'll see |
| --- | --- | --- | --- |
| `alice@acme.test` | Acme | Admin | Full capability-gated nav |
| `bob@acme.test` | Acme | Learner | Reduced nav (Directory, Skills) |
| `dana@shared.test` | Acme + Northwind | Learner / Manager | Signs in via the **tenant picker** |

Sign in at http://localhost:5173, then open **Directory** for the paginated, tenant-scoped
people list. `seed_demo` is idempotent — safe to re-run.

> The app tracks the active tenant with an `X-Tenant-Id` header the SPA sends on every
> request. To call the API directly: `POST /api/auth/login/` → use the returned `access`
> token as `Authorization: Bearer <token>` plus `X-Tenant-Id: <tenant_id>` on later calls.

> **Port 8000 in use?** Django defaults to `:8000`. If another service holds it, free that
> port or change it in `ecosystem.config.js` (backend args) and point the frontend's
> `VITE_API_URL` (in `frontend/.env`) at the new port.

## Tests & quality

```bash
make test    # backend pytest + frontend vitest
make lint    # ruff + black + mypy (backend) · oxlint + tsc (frontend)
make format  # auto-format backend
```

## Layout

```
backend/    DRF API — see backend/CLAUDE.md
frontend/   React SPA — see frontend/CLAUDE.md
docs/specs/ Distilled specs (architecture, data-model, phase-1, phase-2, roadmap)
docs/       Original source documents (.docx, .html)
.claude/    Claude Code setup (agents, settings template)
Makefile · docker-compose.yml · ecosystem.config.js
```

## Working with Claude

`CLAUDE.md` (root + `backend/` + `frontend/`) encodes the architecture and the hard rules.
To reduce permission prompts, copy `.claude/settings.json.example` to
`.claude/settings.local.json` (personal) or `.claude/settings.json` (shared) after reviewing it.
