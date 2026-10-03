import { expect, test } from 'vitest'

import { httpError, networkError } from '../test/http'
import { apiErrorMessage, apiErrorStatus } from './errors'

test('reads the raised-exception envelope', () => {
  const err = httpError(400, { error: { code: 'invalid', detail: 'Slug already in use.' } })
  expect(apiErrorMessage(err, 'fallback')).toBe('Slug already in use.')
})

test('reads a bare service-error detail', () => {
  expect(apiErrorMessage(httpError(409, { detail: 'Already invited.' }), 'fallback')).toBe(
    'Already invited.',
  )
})

test('joins DRF field errors, without a label for non-field errors', () => {
  const err = httpError(400, {
    slug: ['Enter a valid slug.'],
    non_field_errors: ['Password too short.'],
  })
  expect(apiErrorMessage(err, 'fallback')).toBe('slug: Enter a valid slug. Password too short.')
})

test('explains an unreachable server instead of blaming the credentials', () => {
  expect(apiErrorMessage(networkError(), 'fallback')).toMatch(/Can't reach the server/)
  expect(apiErrorStatus(networkError())).toBeUndefined()
})

test('falls back for unknown shapes and non-HTTP errors', () => {
  expect(apiErrorMessage(httpError(500, '<html>'), 'fallback')).toBe('fallback')
  expect(apiErrorMessage(new Error('boom'), 'fallback')).toBe('fallback')
  expect(apiErrorStatus(httpError(403))).toBe(403)
})

test('unwraps a nested detail object and lists inside the envelope', () => {
  const nested = httpError(403, {
    error: { code: 'permission_denied', detail: { detail: 'Nope.' } },
  })
  expect(apiErrorMessage(nested)).toBe('Nope.')
  expect(apiErrorMessage(httpError(400, { error: { detail: ['Still granted.'] } }))).toBe(
    'Still granted.',
  )
})

test('labels field errors carried in the envelope', () => {
  const err = httpError(400, {
    error: { code: 'invalid', detail: { principal_id: ['Not a member.'], scope_id: ['Bad.'] } },
  })
  expect(apiErrorMessage(err)).toBe('principal_id: Not a member. scope_id: Bad.')
})

test('defaults the fallback when a screen does not pass one', () => {
  expect(apiErrorMessage(new Error('x'))).toBe('Something went wrong.')
})
