# Features

Feature modules mirror the backend apps (`identity`, `authz`, `skills`, `profiles`).
Each feature folder owns its API hooks (TanStack Query), components, and types for
one domain, so a screen composes features rather than reaching into a global layer.

Suggested layout per feature (create when implementing):

```
features/skills/
  api.ts          # useSkills(), useCreateSkill() — TanStack Query hooks over src/lib/api.ts
  components/      # SkillCard, SkillForm, ...
  types.ts        # Skill, SkillLevel, ...
```

Keep cross-cutting concerns (auth, tenant, query client, axios) in `src/lib/`.
See `docs/specs/phase-1.md` and `docs/specs/phase-2.md` for what each feature ships.
