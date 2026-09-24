# Frontend guide (Vite + React + TS)

React 19 · TypeScript · Vite · Tailwind v4 · React Router · TanStack Query · axios.
Lint via oxlint + `tsc`, tests via Vitest + Testing Library, format via Prettier.

## Layout

```
src/
  main.tsx           mounts <App/>
  App.tsx            composes providers: QueryClient → Auth → Tenant → Router
  router.tsx         routes; public (/login, /choose) vs protected (AppShell children)
  lib/
    api.ts           axios instance: JWT + X-Tenant-Id headers, refresh-on-401 retry
    auth.tsx         AuthProvider, useAuth(), hasCapability()
    tenant.tsx       TenantProvider, useTenant(), runtime accent theming
    queryClient.ts   TanStack Query client + resetForTenantSwitch()
  components/
    AppShell.tsx     one shell: pinned tenant top bar + capability-gated nav
    ProtectedRoute.tsx, PagePlaceholder.tsx
  pages/             LoginPage, ChooseTenantPage, Dashboard, Directory, Skills, Admin, NotFound
  features/          per-domain modules (api hooks + components + types) — see features/README.md
  test/setup.ts      jest-dom matchers
```

## Commands

```bash
cd frontend
npm run dev            # :5173  (or: make frontend)
npm run test           # vitest run
npm run lint           # oxlint + tsc --noEmit
npm run format         # prettier --write
npm run build          # tsc -b && vite build
```

`VITE_API_URL` (in `.env`) points at the backend, default `http://localhost:8000/api`.

## Conventions

- **Capability-gated UI**: the shell hides what the user can't do — don't render dead
  controls. Nav items carry an optional `capability`; add gated sections there.
- **Cache per tenant**: TanStack Query keys must include the tenant where relevant, and
  a tenant switch calls `resetForTenantSwitch()` (already wired in `useTenant().setTenant`).
  Never let one tenant's data leak into another's view.
- **Tenant name is always visible** in the top bar. Accent colour comes from the CSS
  custom property `--tenant-accent` (set at runtime in `tenant.tsx`) — theme with that,
  not hard-coded colours, so tenant branding applies without a rebuild.
- **Pessimistic writes** for anything touching assertions/ledger — explicit confirm, not
  optimistic. Cheap toggles can be optimistic.
- **Feature modules** (`src/features/<domain>/`) own their API hooks over `lib/api.ts`;
  keep cross-cutting concerns in `lib/`.
- Data fetching goes through TanStack Query hooks, not ad-hoc `useEffect` + axios.
- Keep Prettier + oxlint clean. The two `only-export-components` warnings on the provider
  files are expected (a provider + its hook live together) and are safe to ignore.
