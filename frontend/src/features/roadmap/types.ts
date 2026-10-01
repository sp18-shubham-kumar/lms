/**
 * Types for the learner roadmap — the "Path" direction's hero surface.
 *
 * These shapes are UI-facing. When the backend lands, a TanStack Query hook
 * (`useRoadmap()`) returns this shape and the fixture import goes away; the
 * components below never change. See fixtures.ts.
 */

/** Ordinal skill levels. 0 = not started; 1..4 = Aware → Expert. */
export type LevelValue = 0 | 1 | 2 | 3 | 4

export const LEVEL_NAMES = ['—', 'Aware', 'Working', 'Proficient', 'Expert'] as const

export type StepStatus = 'cleared' | 'current' | 'upcoming'

export interface StepResource {
  title: string
  /** e.g. "Course", "Article", "Workshop". */
  kind: string
  duration: string
  modulesDone: number
  modulesTotal: number
}

export interface RoadmapStep {
  id: string
  skill: string
  /** Target level for this step, as an ordinal. */
  targetLevel: LevelValue
  /** The learner's current level in this skill, as an ordinal. */
  currentLevel: LevelValue
  status: StepStatus
  /** Short line under a cleared/upcoming step (e.g. "Verified by Anita Rao"). */
  note?: string
  /** Levels still to gain to clear this step (for the current step). */
  levelsToGo?: number
  /** The next thing to actually do — only the current step carries one. */
  resource?: StepResource
}

export interface Roadmap {
  learner: string
  targetGrade: string
  /** 0–100. */
  readiness: number
  milestonesCleared: number
  milestonesTotal: number
  steps: RoadmapStep[]
}

// --- API shapes (GET /api/profiles/*) --------------------------------------

export interface JobProfile {
  id: string
  tenant: string
  track: string
  grade: number
  title: string
  status: string
  version: number
  created_at: string
  updated_at: string
}

export interface ReadinessRequirement {
  skill_id: string
  skill_name: string
  criticality: string
  min_level: number
  current_level: number | null
  status: 'met' | 'close' | 'not_started'
}

export interface Readiness {
  job_profile: string
  readiness_pct: number
  met: number
  total: number
  requirements: ReadinessRequirement[]
}
