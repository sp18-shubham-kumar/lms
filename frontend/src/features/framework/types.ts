/**
 * Types mirroring the skill framework authoring API (snake_case, exact shapes).
 * See /api/skills/{id}/levels|edges|versions|override and /api/skills/overrides/.
 */
import type { ApiSkill } from '../skills/types'

export type SkillStatus = 'draft' | 'published' | 'retired'

/** One rung of a skill's rubric grid. */
export interface SkillLevel {
  id?: string
  level: number
  title: string
  indicators: string[]
  evidence_kinds: string[]
  min_verifier_level: number | null
  validity_months: number | null
}

export type EdgeKind = 'prerequisite' | 'adjacent'

export interface SkillEdge {
  id: string
  from_skill: string
  to_skill: string
  kind: EdgeKind
}

export interface SkillOverride {
  id: string
  skill: string
  /** The skill's own name, before this tenant's rename. */
  skill_name: string
  name: string
  status: string
  hidden: boolean
}

export interface SkillInput {
  domain: string
  name: string
  slug: string
  external_code?: string
  description?: string
}

/** A skill row is editable in place only while it's a draft the tenant owns. */
export function isEditable(skill: ApiSkill): boolean {
  return skill.tenant !== null && skill.status === 'draft'
}

export function isGlobal(skill: ApiSkill): boolean {
  return skill.tenant === null
}

/** Rubric rows the grid offers (the backend accepts levels 1..5). */
export const RUBRIC_LEVELS = [1, 2, 3, 4, 5] as const

export function slugify(name: string): string {
  return name
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
}

/** Keep the highest version of each (owner, slug) skill. */
export function latestVersions(skills: ApiSkill[]): ApiSkill[] {
  const latest = new Map<string, ApiSkill>()
  for (const skill of skills) {
    const key = `${skill.tenant ?? 'global'}:${skill.slug}`
    const seen = latest.get(key)
    if (!seen || skill.version > seen.version) latest.set(key, skill)
  }
  return [...latest.values()].sort((a, b) => a.name.localeCompare(b.name))
}
