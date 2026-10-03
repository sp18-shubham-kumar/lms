import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../../../lib/api'
import { mockSession, page, renderWithProviders } from '../../../test/renderWithProviders'
import { GrantsPanel } from './GrantsPanel'

const GRANT = {
  id: 'g1',
  principal_type: 'person',
  principal_id: 'p1',
  role: 'r1',
  role_name: 'Manager',
  scope_type: 'org_unit',
  scope_id: 'o1',
}

function mockApi() {
  return vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.includes('grants')) return page([GRANT])
    if (url.includes('roles')) return page([{ id: 'r2', name: 'Learner', capabilities: [] }])
    if (url.includes('org-units')) return page([{ id: 'o1', name: 'Data', path: 'data' }])
    return page([{ id: 'p1', email: 'ann@acme.test', display_name: 'Ann' }])
  }) as never)
}

afterEach(() => vi.restoreAllMocks())

test('lists the person’s grants with role and scope, and revokes after confirm', async () => {
  mockSession(['member.invite', 'member.offboard', 'directory.view'])
  const get = mockApi()
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null } as never)
  renderWithProviders(<GrantsPanel personId="p1" onPersonChange={vi.fn()} />)
  expect(await screen.findByText('Manager')).toBeInTheDocument()
  expect(await screen.findByText('· Data')).toBeInTheDocument()
  expect(get).toHaveBeenCalledWith('/authz/grants/', {
    params: { principal_id: 'p1', page_size: 200 },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Revoke' }))
  fireEvent.click(screen.getByRole('button', { name: 'Revoke Manager?' }))
  await waitFor(() => expect(del).toHaveBeenCalledWith('/authz/grants/g1/'))
})

test('hides revoke without member.offboard', async () => {
  mockSession(['member.invite', 'directory.view'])
  mockApi()
  renderWithProviders(<GrantsPanel personId="p1" onPersonChange={vi.fn()} />)
  expect(await screen.findByText('Manager')).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Revoke' })).not.toBeInTheDocument()
})

test('grants a role scoped to an org unit', async () => {
  mockSession(['member.invite', 'directory.view'])
  mockApi()
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: GRANT } as never)
  renderWithProviders(<GrantsPanel personId="p1" onPersonChange={vi.fn()} />)
  await screen.findByRole('option', { name: 'Learner' })
  await screen.findByRole('option', { name: 'data' })
  fireEvent.change(screen.getByLabelText('Role'), { target: { value: 'r2' } })
  fireEvent.change(screen.getByLabelText('Scope'), { target: { value: 'org_unit' } })
  const grantButton = screen.getByRole('button', { name: 'Grant role' })
  expect(grantButton).toBeDisabled() // scope chosen but no org unit yet
  fireEvent.change(screen.getByLabelText('Org unit'), { target: { value: 'o1' } })
  fireEvent.click(grantButton)
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/authz/grants/', {
      principal_id: 'p1',
      role: 'r2',
      scope_type: 'org_unit',
      scope_id: 'o1',
    }),
  )
})
