/** Test helpers: a retry-free QueryClient + router, and auth/tenant spies. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'

import * as authModule from '../lib/auth'
import * as tenantModule from '../lib/tenant'

export function renderWithProviders(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>,
  )
}

/** Stub the session with exactly these capabilities, in tenant t1. */
export function mockSession(capabilities: string[]) {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => capabilities.includes(c),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
}

export const page = (results: unknown[]) => ({
  data: { count: results.length, next: null, previous: null, results },
})
