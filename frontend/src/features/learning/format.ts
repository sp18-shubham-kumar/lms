/** Display helpers shared by the learning screens. */
import axios from 'axios'

import { KIND_LABELS, type LearningProgress, type ResourceSummary } from './types'

export function formatDuration(minutes: number | null): string | null {
  if (!minutes) return null
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (!hours) return `${rest} min`
  return rest ? `${hours} h ${rest} min` : `${hours} h`
}

/** "Course · 4 h · 2 of 6 modules" — the line under a resource's title. */
export function resourceMeta(resource: ResourceSummary, progress?: LearningProgress | null) {
  const total = resource.module_count
  const modules =
    progress && progress.status !== 'not_started'
      ? `${progress.completed_modules} of ${total} modules`
      : `${total} ${total === 1 ? 'module' : 'modules'}`
  return [KIND_LABELS[resource.kind], formatDuration(resource.duration_minutes), modules]
    .filter(Boolean)
    .join(' · ')
}

/** Flatten the API error envelope (`{error: {detail}}`) into one readable line. */
export function apiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.error?.detail
    if (typeof detail === 'string') return detail
    if (detail && typeof detail === 'object') {
      return Object.entries(detail)
        .map(([field, messages]) => `${field}: ${JSON.stringify(messages)}`)
        .join('; ')
    }
  }
  return 'Something went wrong. Please try again.'
}
