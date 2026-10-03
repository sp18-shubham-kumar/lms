/**
 * Turn a failed API call into one readable sentence.
 *
 * Raised DRF errors arrive as `{"error": {"code", "detail"}}`, where `detail` is a
 * string, a `{detail}` object, a list, or a field → messages map. Some views still
 * return a bare `{"detail": ...}`. Both are flattened here so screens can show the
 * backend's reason instead of a generic "something went wrong".
 */
import { isAxiosError } from 'axios'

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
  if (!error.response) return 'Could not reach the server. Check that the backend is running.'
  const body = error.response.data as { error?: { detail?: unknown }; detail?: unknown } | undefined
  const messages = flatten(body?.error?.detail ?? body?.detail)
  return messages.length ? messages.join(' ') : fallback
}
