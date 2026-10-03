/**
 * Turn an API failure into one line a person can act on.
 *
 * The backend answers in three shapes: the `{"error": {"code", "detail"}}`
 * envelope from raised exceptions, a bare `{"detail"}` from service errors, and
 * DRF field validation `{"field": ["message", ...]}`. No response at all means the
 * request never reached the server (backend down, wrong VITE_API_URL, or CORS).
 */
import { isAxiosError } from 'axios'

import { API_URL } from './api'

type Body = Record<string, unknown>

function fieldMessages(body: Body): string | null {
  const parts = Object.entries(body).flatMap(([field, value]) => {
    const messages = Array.isArray(value) ? value.filter((v) => typeof v === 'string') : []
    if (messages.length === 0) return []
    return field === 'non_field_errors' ? messages : [`${field}: ${messages.join(' ')}`]
  })
  return parts.length > 0 ? parts.join(' ') : null
}

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback
  if (!error.response) return `Can't reach the server at ${API_URL}. Is the backend running?`
  const body = error.response.data as Body | undefined
  if (!body || typeof body !== 'object') return fallback
  const envelope = body.error as Body | undefined
  if (envelope && typeof envelope.detail === 'string') return envelope.detail
  if (typeof body.detail === 'string') return body.detail
  return fieldMessages(body) ?? fallback
}

/** HTTP status of a failed API call, if the server answered. */
export function apiErrorStatus(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined
}
