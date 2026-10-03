/** Shared harness for the career-path and team screen tests. */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import * as authModule from '../../lib/auth'
import * as tenantModule from '../../lib/tenant'
import type { JobProfile } from './types'

export function renderAt(path: string, routes: Array<{ path: string; element: ReactNode }>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          {routes.map((r) => (
            <Route key={r.path} path={r.path} element={r.element} />
          ))}
          <Route path="*" element={<p>elsewhere</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

export function mockSession(capabilities: string[]) {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => capabilities.includes(c),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
}

export function page<T>(results: T[]) {
  return { data: { count: results.length, next: null, previous: null, results } }
}

export function jobProfile(over: Partial<JobProfile>): JobProfile {
  return {
    id: 'p1',
    tenant: 't1',
    track: 'tr1',
    grade: 2,
    title: 'Data Engineer L2',
    status: 'published',
    version: 1,
    created_at: '2026-09-01T00:00:00Z',
    updated_at: '2026-09-01T00:00:00Z',
    ...over,
  }
}
