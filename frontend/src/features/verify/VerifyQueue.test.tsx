import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { apiError, mockSession, page, renderAt } from '../../test/utils'
import { VerifyQueue } from './VerifyQueue'

const claim = {
  id: 'c1',
  membership: 'm1',
  person_name: 'Ada Lovelace',
  person_email: 'ada@acme.test',
  skill: 's1',
  skill_name: 'SQL',
  level: 2,
  note: 'Built the billing reports',
  review_status: 'pending',
  reviewed_at: null,
  review_note: '',
  created_at: '2026-10-01T00:00:00Z',
}

let get: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  mockSession(['skill.verify'])
  get = vi.spyOn(api, 'get').mockResolvedValue(page([claim]) as never)
})
afterEach(() => vi.restoreAllMocks())

test('verify lets the verifier change the level and waits for an explicit confirm', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)
  renderAt(<VerifyQueue />)

  fireEvent.click(await screen.findByRole('button', { name: 'Verify' }))
  expect(post).not.toHaveBeenCalled()
  const form = screen.getByRole('form', { name: 'Confirm verification' })
  expect(within(form).getByLabelText('Verified level')).toHaveValue('2')
  fireEvent.change(within(form).getByLabelText('Verified level'), { target: { value: '3' } })
  fireEvent.change(within(form).getByLabelText('Note (optional)'), {
    target: { value: 'Reviewed the reports' },
  })
  fireEvent.click(within(form).getByRole('button', { name: 'Confirm L3' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/skills/claims/c1/verify/', {
      level: 3,
      note: 'Reviewed the reports',
    }),
  )
  // The queue is refetched after the server accepts the review.
  await waitFor(() => expect(get).toHaveBeenCalledTimes(2))
})

test('reject requires a reason', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: claim } as never)
  renderAt(<VerifyQueue />)

  fireEvent.click(await screen.findByRole('button', { name: 'Reject' }))
  const confirm = screen.getByRole('button', { name: 'Confirm rejection' })
  expect(confirm).toBeDisabled()
  fireEvent.change(screen.getByLabelText('Reason (shown to the member)'), {
    target: { value: 'No evidence attached' },
  })
  fireEvent.click(confirm)

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/skills/claims/c1/reject/', {
      note: 'No evidence attached',
    }),
  )
})

test('shows the server’s refusal, e.g. reviewing your own claim', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(
    apiError(403, 'You cannot review your own skill claim.', 'permission_denied'),
  )
  renderAt(<VerifyQueue />)

  fireEvent.click(await screen.findByRole('button', { name: 'Verify' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm L2' }))
  expect(await screen.findByRole('alert')).toHaveTextContent(
    'You cannot review your own skill claim.',
  )
})

test('status tabs query the matching review status', async () => {
  renderAt(<VerifyQueue />)
  await screen.findByRole('button', { name: 'Verify' })
  fireEvent.click(screen.getByRole('tab', { name: 'Rejected' }))
  await waitFor(() =>
    expect(get).toHaveBeenLastCalledWith('/skills/claims/', {
      params: { status: 'rejected', page_size: 200 },
    }),
  )
})
