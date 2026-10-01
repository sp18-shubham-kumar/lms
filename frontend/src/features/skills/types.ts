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

/**
 * Human labels for the level scale (index 0 = not declared). The UI meter and
 * declare picker use 1..4 (Aware → Expert); a higher backend level falls back to
 * an "L{n}" label in SkillCard.
 */
export const LEVEL_LABELS = ['—', 'Aware', 'Working', 'Proficient', 'Expert'] as const
