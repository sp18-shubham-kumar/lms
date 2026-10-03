import { screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { mockSession, renderWithProviders } from '../../test/renderWithProviders'
import { PersonProfile } from './PersonProfile'

beforeEach(() => mockSession(['directory.view']))
afterEach(() => vi.restoreAllMocks())

test('renders the person, their skills and readiness', async () => {
  const get = vi.spyOn(api, 'get').mockResolvedValue({
    data: {
      id: 'p1',
      email: 'ann@acme.test',
      display_name: 'Ann Lee',
      status: 'active',
      joined_at: null,
      org_unit: { id: 'o1', name: 'Data', path: 'data' },
      declared: [{ skill_id: 's1', skill_name: 'SQL', level: 2, note: '' }],
      verified: [{ skill_id: 's2', skill_name: 'Python', level: 3, verified_at: null }],
      readiness: [
        {
          job_profile_id: 'j1',
          job_profile_name: 'Data Engineer L2',
          met: 1,
          total: 2,
          readiness_pct: 50,
          computed_at: '2026-10-01T00:00:00Z',
        },
      ],
    },
  } as never)
  renderWithProviders(<PersonProfile personId="p1" />)
  expect(await screen.findByRole('heading', { name: 'Ann Lee' })).toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/identity/people/p1/')
  expect(screen.getByText('SQL')).toBeInTheDocument()
  expect(screen.getByText('Python')).toBeInTheDocument()
  expect(screen.getByText('Data Engineer L2')).toBeInTheDocument()
})

test('shows the API error instead of an empty profile', async () => {
  vi.spyOn(api, 'get').mockRejectedValue({
    isAxiosError: true,
    response: { status: 404, data: { error: { code: 'not_found', detail: 'Not found.' } } },
  })
  renderWithProviders(<PersonProfile personId="p9" />)
  expect(await screen.findByText(/Not found\./)).toBeInTheDocument()
})
