/**
 * Shared test plumbing: a fresh QueryClient + MemoryRouter per render, auth and
 * tenant hooks mocked, and helpers for paginated and error API responses.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { AxiosError, type AxiosResponse } from 'axios'
import type { ReactElement } from 'react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { vi } from 'vitest'

import * as authModule from '../lib/auth'
import * as tenantModule from '../lib/tenant'

export function mockSession(capabilities: string[]) {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => capabilities.includes(c),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
}

/** Render `ui` at `path`, matched against `route` (so `useParams` works). */
export function renderAt(ui: ReactElement, { path = '/', route = '/' } = {}) {
  const qc = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={ui} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

export const page = (results: unknown[]) => ({
  data: { count: results.length, next: null, previous: null, results },
})

/** An axios failure carrying the backend's `{"error": {"code", "detail"}}` envelope. */
export function apiError(status: number, detail: unknown, code = 'invalid') {
  return new AxiosError('Request failed', 'ERR_BAD_REQUEST', undefined, undefined, {
    status,
    data: { error: { code, detail } },
  } as AxiosResponse)
}

export function skill(overrides: Record<string, unknown> = {}) {
  return {
    id: 's1',
    tenant: 't1',
    domain: 'd1',
    name: 'SQL',
    slug: 'sql',
    external_code: '',
    description: '',
    status: 'draft',
    version: 1,
    ...overrides,
  }
}
