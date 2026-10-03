import { expect, test } from 'vitest'

import { apiError } from '../test/utils'
import { apiErrorMessage } from './apiError'

test('uses the envelope detail string', () => {
  expect(apiErrorMessage(apiError(400, 'This prerequisite edge would create a cycle.'))).toBe(
    'This prerequisite edge would create a cycle.',
  )
})

test('flattens field maps and lists, prefixing field names', () => {
  const error = apiError(400, { slug: ['Already taken.'], non_field_errors: ['Bad.'] })
  expect(apiErrorMessage(error)).toBe('slug: Already taken. Bad.')
})

test('falls back for non-API errors and empty bodies', () => {
  expect(apiErrorMessage(new Error('boom'), 'Nope.')).toBe('Nope.')
  expect(apiErrorMessage(apiError(500, undefined), 'Nope.')).toBe('Nope.')
})
