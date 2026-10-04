import { screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { mockSession, page, renderWithProviders } from '../../test/renderWithProviders'
import { AdminConsole } from './AdminConsole'

afterEach(() => vi.restoreAllMocks())

test('only shows tabs the caller has the capability for', () => {
  mockSession(['directory.view'])
  vi.spyOn(api, 'get').mockResolvedValue(page([]) as never)
  renderWithProviders(<AdminConsole />)
  const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
  expect(tabs).toEqual(['Members'])
})

test('new tabs can be appended to the array', () => {
  mockSession([])
  renderWithProviders(
    <AdminConsole tabs={[{ id: 'invites', label: 'Invitations', render: () => <p>invites</p> }]} />,
  )
  expect(screen.getByRole('tab', { name: 'Invitations' })).toHaveAttribute('aria-selected', 'true')
  expect(screen.getByText('invites')).toBeInTheDocument()
})

test('admins who can invite get the Invitations tab next to Members', () => {
  mockSession(['directory.view', 'member.invite'])
  vi.spyOn(api, 'get').mockResolvedValue(page([]) as never)
  renderWithProviders(<AdminConsole />)
  const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
  expect(tabs).toEqual(['Members', 'Invitations', 'Roles', 'Grants', 'Import'])
})
