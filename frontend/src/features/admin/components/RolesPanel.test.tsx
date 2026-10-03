import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../../lib/api'
import { mockSession, page, renderWithProviders } from '../../../test/renderWithProviders'
import { RolesPanel } from './RolesPanel'

const ROLE = { id: 'r1', name: 'Manager', is_system: false, capabilities: ['directory.view'] }

beforeEach(() => {
  mockSession(['member.invite'])
  vi.spyOn(api, 'get').mockImplementation((async (url: string) =>
    url.includes('capabilities')
      ? { data: [{ key: 'directory.view' }, { key: 'report.org.view' }] }
      : page([ROLE])) as never)
})
afterEach(() => vi.restoreAllMocks())

test('creating a role posts the name and checked capabilities', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: ROLE } as never)
  renderWithProviders(<RolesPanel />)
  fireEvent.click(await screen.findByRole('button', { name: 'New role' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: ' Analyst ' } })
  fireEvent.click(await screen.findByLabelText('report.org.view'))
  fireEvent.click(screen.getByRole('button', { name: 'Create role' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/authz/roles/', {
      name: 'Analyst',
      capabilities: ['report.org.view'],
    }),
  )
})

test('editing a role patches it and shows the backend error', async () => {
  const patch = vi.spyOn(api, 'patch').mockRejectedValue({
    isAxiosError: true,
    response: { status: 400, data: { error: { code: 'invalid', detail: { name: ['Taken.'] } } } },
  })
  renderWithProviders(<RolesPanel />)
  fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
  fireEvent.click(await screen.findByLabelText('report.org.view'))
  fireEvent.click(screen.getByRole('button', { name: 'Save role' }))
  await waitFor(() =>
    expect(patch).toHaveBeenCalledWith('/authz/roles/r1/', {
      name: 'Manager',
      capabilities: ['directory.view', 'report.org.view'],
    }),
  )
  expect(await screen.findByText('name: Taken.')).toBeInTheDocument()
})

test('delete asks for confirmation first', async () => {
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null } as never)
  renderWithProviders(<RolesPanel />)
  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(del).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Delete Manager?' }))
  await waitFor(() => expect(del).toHaveBeenCalledWith('/authz/roles/r1/'))
})
