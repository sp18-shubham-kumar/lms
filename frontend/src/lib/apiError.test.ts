import { AxiosError, AxiosHeaders } from 'axios'
import { expect, test } from 'vitest'

import { apiErrorMessage } from './apiError'

function axiosError(status: number, data: unknown) {
  return new AxiosError('fail', 'ERR', undefined, undefined, {
    status,
    statusText: '',
    headers: {},
    config: { headers: new AxiosHeaders() },
    data,
  })
}

test('reads the wrapped error envelope', () => {
  const err = axiosError(409, { error: { code: 'profile_not_editable', detail: 'Locked.' } })
  expect(apiErrorMessage(err, 'x')).toBe('Locked.')
})

test('flattens field validation errors with their field names', () => {
  const err = axiosError(400, {
    error: { code: 'invalid', detail: { min_level: ['Too big.'], non_field_errors: ['Nope.'] } },
  })
  expect(apiErrorMessage(err, 'x')).toBe('min_level: Too big. Nope.')
})

test('reads a bare detail body', () => {
  expect(apiErrorMessage(axiosError(400, { detail: 'Bad.' }), 'x')).toBe('Bad.')
})

test('falls back for non-API errors and empty bodies', () => {
  expect(apiErrorMessage(new Error('boom'), 'Fallback')).toBe('Fallback')
  expect(apiErrorMessage(axiosError(500, ''), 'Fallback')).toBe('Fallback')
})
