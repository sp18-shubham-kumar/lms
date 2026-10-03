import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import * as authModule from '../../lib/auth'
import * as tenantModule from '../../lib/tenant'
import { RoadmapHome } from './RoadmapHome'

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

function mockAuth(cap: boolean) {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({ hasCapability: () => cap } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
}

const readiness = {
  job_profile: 'p2',
  readiness_pct: 50,
  met: 1,
  total: 2,
  requirements: [
    {
      skill_id: 's1',
      skill_name: 'SQL',
      criticality: 'core',
      min_level: 2,
      current_level: 2,
      status: 'met',
    },
    {
      skill_id: 's2',
      skill_name: 'Python',
      criticality: 'core',
      min_level: 2,
      current_level: 1,
      status: 'close',
    },
  ],
}

const recommendations = {
  job_profile: 'p2',
  gaps: [
    {
      skill_id: 's2',
      skill_name: 'Python',
      criticality: 'core',
      min_level: 2,
      current_level: 1,
      resources: [
        {
          resource: {
            id: 'r1',
            title: 'Intermediate Python for Data',
            kind: 'course',
            url: '',
            provider: '',
            module_count: 6,
            duration_minutes: null,
            status: 'published',
          },
          target_level: 2,
          progress: null,
        },
      ],
    },
  ],
}

beforeEach(() => {
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.includes('job-profiles'))
      return {
        data: {
          count: 1,
          next: null,
          previous: null,
          results: [{ id: 'p2', title: 'Data Engineer L2' }],
        },
      }
    if (url.includes('recommendations')) return { data: recommendations }
    return { data: readiness }
  }) as never)
})

test('member without directory.view sees guidance, not a picker', () => {
  mockAuth(false)
  render(wrap(<RoadmapHome />))
  expect(screen.getByText(/target grade hasn’t been shared/i)).toBeInTheDocument()
})

test('picking a target renders real readiness', async () => {
  mockAuth(true)
  render(wrap(<RoadmapHome />))
  // Wait for the profiles to load so the option exists before selecting it.
  await screen.findByRole('option', { name: 'Data Engineer L2' })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'p2' } })
  expect(await screen.findByLabelText(/Readiness 50 percent/)).toBeInTheDocument()
  expect(screen.getByText(/1 of 2 core requirements met/)).toBeInTheDocument()
  expect(screen.getByText(/Now · Python/)).toBeInTheDocument()
})

test('the current gap step lists its recommended resources', async () => {
  mockAuth(true)
  render(wrap(<RoadmapHome />))
  await screen.findByRole('option', { name: 'Data Engineer L2' })
  fireEvent.change(screen.getByRole('combobox'), { target: { value: 'p2' } })
  expect(await screen.findByText('Intermediate Python for Data')).toBeInTheDocument()
  expect(screen.getByText('Course · 6 modules')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Start' })).toBeInTheDocument()
})
