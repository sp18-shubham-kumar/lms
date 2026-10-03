/**
 * Types mirroring the backend learning API (snake_case fields, exact shapes).
 * See /api/learning/resources/, /api/learning/me/progress/,
 * /api/learning/me/recommendations/.
 */

export type ResourceKind = 'course' | 'article' | 'video' | 'book' | 'other'
export type ResourceStatus = 'draft' | 'published' | 'archived'
export type ProgressStatus = 'not_started' | 'in_progress' | 'completed'

export const RESOURCE_KINDS: ResourceKind[] = ['course', 'article', 'video', 'book', 'other']
export const RESOURCE_STATUSES: ResourceStatus[] = ['draft', 'published', 'archived']

export const KIND_LABELS: Record<ResourceKind, string> = {
  course: 'Course',
  article: 'Article',
  video: 'Video',
  book: 'Book',
  other: 'Resource',
}

/** A skill a resource teaches, and the level (1..5) it teaches toward. */
export interface ResourceSkillLink {
  skill: string
  skill_name: string
  level: number
}

export interface LearningResource {
  id: string
  title: string
  kind: ResourceKind
  url: string
  provider: string
  description: string
  module_count: number
  duration_minutes: number | null
  status: ResourceStatus
  skills: ResourceSkillLink[]
  created_at: string
  updated_at: string
}

/** The compact resource shape embedded in progress and recommendations. */
export type ResourceSummary = Pick<
  LearningResource,
  'id' | 'title' | 'kind' | 'url' | 'provider' | 'module_count' | 'duration_minutes' | 'status'
>

export interface LearningProgress {
  id: string
  resource: string
  resource_detail: ResourceSummary
  status: ProgressStatus
  completed_modules: number
  started_at: string | null
  completed_at: string | null
  updated_at: string
}

export interface RecommendedResource {
  resource: ResourceSummary
  target_level: number
  progress: LearningProgress | null
}

export interface RecommendationGap {
  skill_id: string
  skill_name: string
  criticality: string
  min_level: number
  current_level: number | null
  /** Resources that teach beyond the learner's current level, best first. */
  resources: RecommendedResource[]
  /** Resources for the skill that stop at or below the current level. */
  refreshers: RecommendedResource[]
}

export interface Recommendations {
  job_profile: string
  gaps: RecommendationGap[]
}

export interface ResourceFilters {
  skill?: string
  kind?: string
  status?: string
}

/** Create/update body: the resource fields plus its skill links (without names). */
export interface ResourceInput {
  title: string
  kind: ResourceKind
  url: string
  provider: string
  description: string
  module_count: number
  duration_minutes: number | null
  status: ResourceStatus
  skills: { skill: string; level: number }[]
}
