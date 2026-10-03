import { AxiosError, AxiosHeaders } from 'axios'
import { expect, test } from 'vitest'

import { apiErrorMessage } from './apiError'

function failed(status: number, data: unknown) {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError('fail', 'ERR', config, null, {
    status,
    statusText: '',
    headers: {},
    config,
    data,
  })
}

test('reads the detail out of the error envelope', () => {
  const err = failed(403, { error: { code: 'permission_denied', detail: { detail: 'Nope.' } } })
  expect(apiErrorMessage(err)).toBe('Nope.')
})

test('labels field errors and joins them', () => {
  const err = failed(400, {
    error: { code: 'invalid', detail: { principal_id: ['Not a member.'], scope_id: ['Bad.'] } },
  })
  expect(apiErrorMessage(err)).toBe('principal_id: Not a member. scope_id: Bad.')
})

test('handles a bare detail and a list body', () => {
  expect(apiErrorMessage(failed(400, { detail: 'Expired.' }))).toBe('Expired.')
  expect(apiErrorMessage(failed(400, { error: { detail: ['Still granted.'] } }))).toBe(
    'Still granted.',
  )
})

test('explains a network failure and falls back otherwise', () => {
  const config = { headers: new AxiosHeaders() }
  expect(apiErrorMessage(new AxiosError('net', 'ERR_NETWORK', config))).toMatch(/reach the server/)
  expect(apiErrorMessage(new Error('x'), 'Fallback.')).toBe('Fallback.')
})
