/**
 * Turn an API failure into a sentence a person can act on.
 *
 * The backend wraps raised errors as `{"error": {"code", "detail"}}`, where
 * `detail` is a string, a list of strings, or a field → messages map (DRF
 * validation). Some endpoints still answer with a bare `{"detail": ...}`.
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

export function apiErrorMessage(error: unknown, fallback: string): string {
  if (!isAxiosError(error)) return fallback
  const body = error.response?.data as
    { error?: { detail?: unknown }; detail?: unknown } | undefined
  const messages = flatten(body?.error?.detail ?? body?.detail)
  return messages.length ? messages.join(' ') : fallback
}
