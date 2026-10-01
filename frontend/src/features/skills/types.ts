/**
 * Types mirroring the backend skills API (snake_case fields, exact shapes).
 * See GET /api/skills/, /api/skills/domains/, /api/skills/me/declarations/.
 */

export interface SkillDomain {
  id: string
  tenant: string | null
  name: string
  sort: number
}

export interface ApiSkill {
  id: string
  tenant: string | null
  domain: string
  name: string
  slug: string
  external_code: string
  description: string
  status: string
  version: number
}

/** A self-claimed skill (the self-declared confidence tier). */
export interface SelfDeclaration {
  id: string
  membership: string
  skill: string
  level: number
  note: string
}

/** Human labels for the 1..5 level scale (level 0 = not declared). */
export const LEVEL_LABELS = ['—', 'Aware', 'Working', 'Proficient', 'Expert', 'Master'] as const
