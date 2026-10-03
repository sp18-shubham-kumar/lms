import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { jobProfile, mockSession, page, renderAt } from '../career-paths/testUtils'
import { MemberReadinessPage } from './MemberReadinessPage'

let get: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  get = vi.spyOn(api, 'get').mockImplementation((async (
    url: string,
    config?: { params?: { target?: string } },
  ) => {
    if (url === '/profiles/job-profiles/')
      return page([
        jobProfile({ id: 'l2', title: 'Data Engineer L2' }),
        jobProfile({ id: 'l3', grade: 3, title: 'Data Engineer L3' }),
      ])
    const l3 = config?.params?.target === 'l3'
    return {
      data: {
        membership_id: 'm-bob',
        display_name: 'Bob Learner',
        job_profile: config?.params?.target,
        readiness_pct: l3 ? 0 : 50,
        met: l3 ? 0 : 1,
        total: 2,
        requirements: [
          {
            skill_id: 's1',
            skill_name: 'SQL',
            criticality: 'core',
            min_level: 2,
            current_level: 2,
            status: l3 ? 'close' : 'met',
          },
          {
            skill_id: 's2',
            skill_name: 'Python',
            criticality: 'core',
            min_level: 3,
            current_level: 1,
            status: 'close',
          },
        ],
      },
    }
  }) as never)
})

afterEach(() => vi.restoreAllMocks())

const routes = [{ path: '/team/members/:membershipId', element: <MemberReadinessPage /> }]

test('shows the member’s readiness against the target in the link', async () => {
  mockSession(['report.org.view', 'directory.view'])
  render(renderAt('/team/members/m-bob?target=l2', routes))
  expect(await screen.findByLabelText(/Readiness 50 percent/)).toBeInTheDocument()
  expect(screen.getByText(/Bob Learner/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Data Engineer L2' })).toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/profiles/members/m-bob/readiness/', {
    params: { target: 'l2' },
  })
})

test('changing the target recomputes against the new grade', async () => {
  mockSession(['report.org.view', 'directory.view'])
  render(renderAt('/team/members/m-bob?target=l2', routes))
  await screen.findByLabelText(/Readiness 50 percent/)
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'l3' } })
  expect(await screen.findByLabelText(/Readiness 0 percent/)).toBeInTheDocument()
  expect(screen.getByRole('heading', { name: 'Data Engineer L3' })).toBeInTheDocument()
})

test('without report.org.view nothing is fetched', () => {
  mockSession(['directory.view'])
  render(renderAt('/team/members/m-bob?target=l2', routes))
  expect(screen.getByText(/report.org.view/)).toBeInTheDocument()
  expect(get).not.toHaveBeenCalled()
})
