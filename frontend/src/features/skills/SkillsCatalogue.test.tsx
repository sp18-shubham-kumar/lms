import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import { beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import * as authModule from '../../lib/auth'
import * as tenantModule from '../../lib/tenant'
import { SkillsCatalogue } from './SkillsCatalogue'

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>
}

const page = (results: unknown[]) => ({
  data: { count: results.length, next: null, previous: null, results },
})

beforeEach(() => {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({ hasCapability: () => true } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.includes('domains')) return page([{ id: 'd1', tenant: null, name: 'Data', sort: 0 }])
    if (url.includes('declarations')) return page([])
    return page([
      {
        id: 's1',
        tenant: null,
        domain: 'd1',
        name: 'SQL',
        slug: 'sql',
        external_code: '',
        description: '',
        status: 'published',
        version: 1,
      },
    ])
  }) as never)
})

test('renders skills from the API and offers a declare action', async () => {
  render(wrap(<SkillsCatalogue />))
  expect(await screen.findByText('SQL')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Declare/ })).toBeInTheDocument()
})
