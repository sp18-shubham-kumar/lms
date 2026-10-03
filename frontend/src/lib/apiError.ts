/**
 * Turn an API failure into one human sentence.
 *
 * The backend's error envelope is `{"error": {"code", "detail"}}`, where `detail`
 * is whatever DRF raised: a string, a list of messages, or a `{field: [msgs]}`
 * map. A few endpoints still return a bare `{"detail": ...}`. Both are handled so
 * a screen can show the server's actual reason (e.g. "This prerequisite edge
 * would create a cycle.") instead of a generic failure.
 */
import { isAxiosError } from 'axios'

function flatten(detail: unknown): string[] {
  if (detail == null) return []
  if (typeof detail === 'string') return [detail]
  if (Array.isArray(detail)) return detail.flatMap(flatten)
  if (typeof detail === 'object') {
    return Object.entries(detail as Record<string, unknown>).flatMap(([field, value]) =>
      flatten(value).map((msg) =>
        field === 'detail' || field === 'non_field_errors' ? msg : `${field}: ${msg}`,
      ),
    )
  }
  return [String(detail)]
}

export function apiErrorMessage(error: unknown, fallback = 'Something went wrong.'): string {
  if (!isAxiosError(error)) return fallback
  const body = error.response?.data as
    { error?: { detail?: unknown }; detail?: unknown } | undefined
  const messages = flatten(body?.error?.detail ?? body?.detail)
  return messages.length > 0 ? messages.join(' ') : fallback
}
