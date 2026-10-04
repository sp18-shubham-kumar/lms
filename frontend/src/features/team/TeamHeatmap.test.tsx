import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { jobProfile, mockSession, page, renderAt } from '../career-paths/testUtils'
import { TeamHeatmap } from './TeamHeatmap'

let get: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  get = vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url === '/identity/org-units/') return page([{ id: 'ou1', name: 'Data', path: '/data' }])
    if (url === '/profiles/job-profiles/')
      return page([jobProfile({ id: 'v1', version: 1 }), jobProfile({ id: 'v2', version: 2 })])
    return {
      data: {
        columns: [
          { skill_id: 's1', skill_name: 'SQL' },
          { skill_id: 's2', skill_name: 'Python' },
        ],
        rows: [
          { membership_id: 'm-ana', display_name: 'Ana', cells: [{ met: true }, { met: false }] },
          { membership_id: 'm-bo', display_name: 'Bo', cells: [{ met: false }, { met: false }] },
          { membership_id: 'm-cy', display_name: 'Cy', cells: [{ met: true }, { met: true }] },
        ],
      },
    }
  }) as never)
})

afterEach(() => vi.restoreAllMocks())

const routes = [{ path: '/team', element: <TeamHeatmap /> }]

test('targets the newest published version and asks the API for published only', async () => {
  mockSession(['report.org.view'])
  render(renderAt('/team', routes))
  await screen.findByText('Ana')
  expect(get).toHaveBeenCalledWith('/profiles/job-profiles/', {
    params: { page_size: 200, status: 'published' },
  })
  expect(get).toHaveBeenCalledWith('/profiles/heatmap/', {
    params: { org_unit: 'ou1', job_profile: 'v2' },
  })
})

test('member names link to their gap view for the chosen target', async () => {
  mockSession(['report.org.view'])
  render(renderAt('/team', routes))
  expect(await screen.findByRole('link', { name: 'Ana' })).toHaveAttribute(
    'href',
    '/team/members/m-ana?target=v2',
  )
})

test('"One gap from promotion" keeps only members missing exactly one requirement', async () => {
  mockSession(['report.org.view'])
  render(renderAt('/team', routes))
  await screen.findByText('Bo')
  fireEvent.click(screen.getByRole('checkbox', { name: 'One gap from promotion' }))
  expect(screen.getByText('Ana')).toBeInTheDocument()
  expect(screen.queryByText('Bo')).not.toBeInTheDocument()
  expect(screen.queryByText('Cy')).not.toBeInTheDocument()
})
