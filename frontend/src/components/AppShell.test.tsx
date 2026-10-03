import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { AppShell } from './AppShell'
import * as authModule from '../lib/auth'
import * as tenantModule from '../lib/tenant'

const ACME = { tenant_id: 't', slug: 'acme', name: 'Acme', accent_color: '' }

function mockAuth(session: Partial<authModule.Session>, capabilities: string[] = []) {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => capabilities.includes(c),
    logout: vi.fn(),
    session: { capabilities, memberships: [], isPlatformOperator: false, ...session },
    isAuthenticated: true,
    login: vi.fn(),
    loadSession: vi.fn(),
    loadAccount: vi.fn(),
  } as never)
}

function mockTenant(tenant: { id: string; name: string } | null) {
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({ tenant, setTenant: vi.fn() } as never)
}

function renderShell() {
  render(
    <MemoryRouter>
      <Routes>
        <Route path="/" element={<AppShell />} />
        <Route path="/choose" element={<p>choose</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

afterEach(() => vi.restoreAllMocks())

test('nav hides items the user lacks capability for', () => {
  mockAuth({ memberships: [ACME] }, ['directory.view'])
  mockTenant({ id: 't', name: 'Acme' })
  renderShell()
  expect(screen.getByText('Directory')).toBeInTheDocument()
  expect(screen.queryByText('Admin')).not.toBeInTheDocument()
  expect(screen.queryByText('Platform')).not.toBeInTheDocument()
  expect(screen.queryByText('Switch organization')).not.toBeInTheDocument()
})

test('platform operators get a way back to the platform console', () => {
  mockAuth({ memberships: [ACME], isPlatformOperator: true })
  mockTenant({ id: 't', name: 'Acme' })
  renderShell()
  expect(screen.getByRole('link', { name: 'Platform' })).toHaveAttribute('href', '/platform')
})

test('people in several organizations can switch', () => {
  mockAuth({ memberships: [ACME, { ...ACME, tenant_id: 'u', name: 'Globex' }] })
  mockTenant({ id: 't', name: 'Acme' })
  renderShell()
  expect(screen.getByRole('link', { name: 'Switch organization' })).toHaveAttribute(
    'href',
    '/choose',
  )
})

test('without a selected organization the shell sends you to pick one', () => {
  mockAuth({ memberships: [ACME] })
  mockTenant(null)
  renderShell()
  expect(screen.getByText('choose')).toBeInTheDocument()
})
