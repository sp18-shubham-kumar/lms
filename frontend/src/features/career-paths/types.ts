/**
 * Types mirroring the backend profiles API (GET/POST /api/profiles/*).
 * JobProfile and the readiness shapes live with the roadmap feature that first
 * used them; this module adds what authoring needs.
 */
import type { JobProfile, Readiness } from '../roadmap/types'

export type { JobProfile }

/** Every career-path write (tracks, grades, requirements, publish) needs this. */
export const EDIT_CAPABILITY = 'jobprofile.edit'

export type ProfileStatus = 'draft' | 'published' | 'retired'

export type Criticality = 'core' | 'supporting' | 'optional'

export const CRITICALITIES: Criticality[] = ['core', 'supporting', 'optional']

export const CRITICALITY_HELP: Record<Criticality, string> = {
  core: 'Gates promotion — counted in readiness',
  supporting: 'Advisory — shown, not counted',
  optional: 'Nice to have',
}

/** Skill rubrics run 1..5 (SkillLevel); the backend rejects anything outside. */
export const REQUIREMENT_LEVELS = [1, 2, 3, 4, 5] as const

export interface Track {
  id: string
  tenant: string
  name: string
  created_at: string
  updated_at: string
}

export interface ProfileRequirement {
  id: string
  tenant: string
  job_profile: string
  skill: string
  skill_name: string
  min_level: number
  criticality: Criticality
  created_at: string
  updated_at: string
}

/** One rung of a skill's rubric (GET /api/skills/{id}/levels/). */
export interface SkillLevel {
  id: string
  level: number
  title: string
}

/** A manager's view of one member (GET /api/profiles/members/{id}/readiness/). */
export interface MemberReadiness extends Readiness {
  membership_id: string
  display_name: string
}
