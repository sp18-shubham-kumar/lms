import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import * as tenantModule from '../../lib/tenant'
import { InvitationsPanel } from './InvitationsPanel'

const page = (results: unknown[]) => ({
  data: { count: results.length, next: null, previous: null, results },
})

const PENDING = {
  id: 'i1',
  email: 'pending@acme.test',
  role: 'Learner',
  role_id: 'r2',
  status: 'pending',
  expires_at: '2026-10-10T00:00:00Z',
}

function renderPanel() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <InvitationsPanel />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.includes('roles'))
      return page([
        { id: 'r1', name: 'Tenant Admin', is_system: false, capabilities: [] },
        { id: 'r2', name: 'Learner', is_system: true, capabilities: [] },
      ])
    return page([PENDING])
  }) as never)
})
afterEach(() => vi.restoreAllMocks())

test('invites an email into the chosen role and shows the accept link', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: { ...PENDING, id: 'i2', email: 'new@acme.test', invite_url: 'http://x/accept?token=t' },
  } as never)
  const user = userEvent.setup()
  renderPanel()

  await user.type(screen.getByLabelText('Email'), 'new@acme.test')
  await user.selectOptions(await screen.findByLabelText('Role'), 'Learner')
  await user.click(screen.getByRole('button', { name: 'Send invite' }))

  expect(await screen.findByLabelText('Accept link')).toHaveValue('http://x/accept?token=t')
  expect(post).toHaveBeenCalledWith('/identity/invitations/', {
    email: 'new@acme.test',
    role: 'Learner',
  })
})

test('lists pending invitations and resends with a fresh link', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: { ...PENDING, invite_url: 'http://x/accept?token=fresh' },
  } as never)
  const user = userEvent.setup()
  renderPanel()

  expect(await screen.findByText('pending@acme.test')).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Resend' }))
  expect(await screen.findByLabelText('Accept link')).toHaveValue('http://x/accept?token=fresh')
  expect(post).toHaveBeenCalledWith('/identity/invitations/i1/resend/')
})

test('cancel needs an explicit confirm', async () => {
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null } as never)
  const user = userEvent.setup()
  renderPanel()

  await user.click(await screen.findByRole('button', { name: 'Cancel' }))
  expect(del).not.toHaveBeenCalled()
  await user.click(screen.getByRole('button', { name: 'Keep' }))
  expect(del).not.toHaveBeenCalled()

  await user.click(screen.getByRole('button', { name: 'Cancel' }))
  await user.click(screen.getByRole('button', { name: 'Yes, cancel' }))
  expect(del).toHaveBeenCalledWith('/identity/invitations/i1/')
})
