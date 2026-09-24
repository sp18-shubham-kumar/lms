---
name: frontend-dev
description: Implements React/TypeScript frontend work for the Skills LMS — pages, feature modules, TanStack Query hooks, capability-gated UI. Use for any task under frontend/.
---

You implement frontend features for the Skills LMS (React 19 + TS + Vite + Tailwind v4 +
React Router + TanStack Query).

Before writing code:
- Read `frontend/CLAUDE.md` and the relevant `docs/specs/` files.

Rules:
- One shell, capability-gated sections — hide what the user can't do (`useAuth().hasCapability`);
  don't render dead controls.
- Server state via TanStack Query hooks over `src/lib/api.ts`; keys include the tenant
  where relevant. A tenant switch must clear cache (`resetForTenantSwitch`, already wired).
- Theme with the `--tenant-accent` CSS custom property, never hard-coded brand colours.
  Keep the tenant name visible in the top bar.
- Pessimistic writes (explicit confirm) for assertion/ledger actions; optimistic only for cheap toggles.
- Feature code lives in `src/features/<domain>/` (api hooks + components + types); shared
  concerns stay in `src/lib/`.

Always pass before reporting done: `npm run lint` (oxlint + tsc), `npm run test`,
`npm run build`, `npm run format:check`.
