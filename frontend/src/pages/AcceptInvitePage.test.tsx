import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { api } from '../lib/api'
import { httpError } from '../test/http'
import { AcceptInvitePage } from './AcceptInvitePage'

function renderAccept(url: string) {
  const qc = new QueryClient({ defaultOptions: { mutations: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/invite/accept" element={<AcceptInvitePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

async function fill(password: string, confirm: string) {
  const user = userEvent.setup()
  await user.type(screen.getByLabelText('Password'), password)
  await user.type(screen.getByLabelText('Confirm password'), confirm)
  await user.click(screen.getByRole('button', { name: 'Set password and join' }))
}

afterEach(() => vi.restoreAllMocks())

test('sets the password with the token, then links to sign-in with the email', async () => {
  const post = vi
    .spyOn(api, 'post')
    .mockResolvedValue({ data: { email: 'new@acme.test', tenant_id: 't1' } } as never)
  renderAccept('/invite/accept?token=tok-123')
  await fill('Secret-pass-1', 'Secret-pass-1')

  const signIn = await screen.findByRole('link', { name: 'Sign in' })
  expect(signIn).toHaveAttribute('href', '/login?email=new%40acme.test')
  expect(post).toHaveBeenCalledWith('/auth/invitations/accept/', {
    token: 'tok-123',
    password: 'Secret-pass-1',
  })
})

test('mismatched passwords never reach the server', async () => {
  const post = vi.spyOn(api, 'post')
  renderAccept('/invite/accept?token=tok-123')
  await fill('Secret-pass-1', 'Secret-pass-2')
  expect(await screen.findByRole('alert')).toHaveTextContent("don't match")
  expect(post).not.toHaveBeenCalled()
})

test('shows why the server refused, e.g. an expired link', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(httpError(400, { detail: 'This invitation expired.' }))
  renderAccept('/invite/accept?token=old')
  await fill('Secret-pass-1', 'Secret-pass-1')
  expect(await screen.findByRole('alert')).toHaveTextContent('This invitation expired.')
})

test('a link without a token explains what to do', () => {
  renderAccept('/invite/accept')
  expect(screen.getByRole('heading', { name: 'Invite link incomplete' })).toBeInTheDocument()
  expect(screen.queryByLabelText('Password')).not.toBeInTheDocument()
})
