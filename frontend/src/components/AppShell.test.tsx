import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { expect, test, vi } from 'vitest'

import { AppShell } from './AppShell'
import * as authModule from '../lib/auth'
import * as tenantModule from '../lib/tenant'

test('nav hides items the user lacks capability for', () => {
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (c: string) => c === 'directory.view',
    logout: vi.fn(),
    session: { capabilities: ['directory.view'] },
    isAuthenticated: true,
    login: vi.fn(),
    loadSession: vi.fn(),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)

  render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  )
  expect(screen.getByText('Directory')).toBeInTheDocument()
  expect(screen.queryByText('Admin')).not.toBeInTheDocument()
})
