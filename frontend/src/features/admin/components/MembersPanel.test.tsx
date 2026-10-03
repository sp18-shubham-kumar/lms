import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../../../lib/api'
import { mockSession, page, renderWithProviders } from '../../../test/renderWithProviders'
import { MembersPanel } from './MembersPanel'

const people = [
  { id: 'me', email: 'admin@acme.test', display_name: 'Admin', org_unit: null, status: 'active' },
  { id: 'p1', email: 'ann@acme.test', display_name: 'Ann', org_unit: null, status: 'active' },
]

function mockApi() {
  vi.spyOn(api, 'get').mockImplementation((async (url: string) =>
    url.endsWith('/people/me/') ? { data: { id: 'me' } } : page(people)) as never)
}

afterEach(() => vi.restoreAllMocks())

test('offboard needs a confirm, is not offered on yourself, and calls the API', async () => {
  mockSession(['directory.view', 'member.offboard'])
  mockApi()
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: null } as never)
  renderWithProviders(<MembersPanel onManageAccess={vi.fn()} />)
  expect(await screen.findByText('Ann')).toBeInTheDocument()
  await waitFor(() => expect(screen.getAllByRole('button', { name: 'Offboard' })).toHaveLength(1))
  fireEvent.click(screen.getByRole('button', { name: 'Offboard' }))
  expect(post).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Offboard Ann?' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/identity/people/p1/offboard/'))
})

test('hides offboard without member.offboard; manage access hands off the person', async () => {
  mockSession(['directory.view', 'member.invite'])
  mockApi()
  const onManageAccess = vi.fn()
  renderWithProviders(<MembersPanel onManageAccess={onManageAccess} />)
  expect(await screen.findByText('Ann')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Offboard' })).not.toBeInTheDocument()
  fireEvent.click(screen.getAllByRole('button', { name: 'Manage access' })[1])
  expect(onManageAccess).toHaveBeenCalledWith('p1')
})
