/**
 * Turn an API failure into one line a person can act on.
 *
 * Raised DRF errors arrive as `{"error": {"code", "detail"}}`, where `detail` is a
 * string, a `{detail}` object, a list, or a field → messages map. Service errors
 * return a bare `{"detail"}`, and unwrapped validation returns
 * `{"field": ["message", ...]}`. All three are flattened so screens show the
 * backend's reason (e.g. "This prerequisite edge would create a cycle.") instead
 * of a generic failure. No response at all means the request never reached the
 * server: backend down, wrong VITE_API_URL, or CORS.
 */
import { isAxiosError } from 'axios'

import { API_URL } from './api'

function flatten(value: unknown): string[] {
  if (value == null) return []
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(flatten)
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>).flatMap(([key, inner]) => {
      const messages = flatten(inner)
      const labelled = key !== 'detail' && key !== 'non_field_errors'
      return labelled ? messages.map((m) => `${key}: ${m}`) : messages
    })
  }
  return [String(value)]
}

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!isAxiosError(error)) return fallback
  if (!error.response) return `Can't reach the server at ${API_URL}. Is the backend running?`
  const body = error.response.data as Record<string, unknown> | undefined
  if (!body || typeof body !== 'object') return fallback
  const envelope = body.error as { detail?: unknown } | undefined
  const messages = flatten(envelope?.detail ?? body.detail ?? body)
  return messages.length > 0 ? messages.join(' ') : fallback
}

/** HTTP status of a failed API call, if the server answered. */
export function apiErrorStatus(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined
}
