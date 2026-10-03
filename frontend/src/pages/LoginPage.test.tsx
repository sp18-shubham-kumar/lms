import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../lib/api'
import { AuthProvider } from '../lib/auth'
import { TenantProvider } from '../lib/tenant'
import { httpError, networkError } from '../test/http'
import { LoginPage } from './LoginPage'

const ACME = { tenant_id: 't1', slug: 'acme', name: 'Acme', accent_color: '#0d9488' }
const GLOBEX = { tenant_id: 't2', slug: 'globex', name: 'Globex', accent_color: '' }

function loginResponse(memberships: unknown[], isPlatformOperator = false) {
  return {
    data: {
      access: 'a',
      refresh: 'r',
      person: { display_name: 'Ops' },
      memberships,
      is_platform_operator: isPlatformOperator,
    },
  }
}

function renderLogin(initial = '/login') {
  render(
    <AuthProvider>
      <TenantProvider>
        <MemoryRouter initialEntries={[initial]}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/" element={<p>home</p>} />
            <Route path="/choose" element={<p>choose</p>} />
            <Route path="/platform" element={<p>platform</p>} />
          </Routes>
        </MemoryRouter>
      </TenantProvider>
    </AuthProvider>,
  )
}

async function submit(email = 'x@acme.test') {
  const user = userEvent.setup()
  const emailInput = screen.getByLabelText('Email')
  await user.clear(emailInput)
  await user.type(emailInput, email)
  await user.type(screen.getByLabelText('Password'), 'pw')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

test('a platform operator with no memberships lands on the platform console', async () => {
  vi.spyOn(api, 'post').mockResolvedValue(loginResponse([], true) as never)
  renderLogin()
  await submit()
  expect(await screen.findByText('platform')).toBeInTheDocument()
  expect(localStorage.getItem('lms.tenant')).toBeNull()
})

test('a single membership enters that tenant and loads its session', async () => {
  vi.spyOn(api, 'post').mockResolvedValue(loginResponse([ACME]) as never)
  const get = vi
    .spyOn(api, 'get')
    .mockResolvedValue({ data: { capabilities: [], memberships: [ACME] } } as never)
  renderLogin()
  await submit()
  expect(await screen.findByText('home')).toBeInTheDocument()
  expect(localStorage.getItem('lms.tenant')).toBe('t1')
  expect(get).toHaveBeenCalledWith('/auth/session/')
})

test('an operator who is also a member chooses between org and platform', async () => {
  vi.spyOn(api, 'post').mockResolvedValue(loginResponse([ACME], true) as never)
  renderLogin()
  await submit()
  expect(await screen.findByText('choose')).toBeInTheDocument()
})

test('several memberships go to the organization picker', async () => {
  vi.spyOn(api, 'post').mockResolvedValue(loginResponse([ACME, GLOBEX]) as never)
  renderLogin()
  await submit()
  expect(await screen.findByText('choose')).toBeInTheDocument()
})

test('a person with no membership is told to get invited, not that the password is wrong', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(
    httpError(403, { error: { detail: 'You have no active membership in any organization.' } }),
  )
  renderLogin()
  await submit()
  expect(await screen.findByRole('alert')).toHaveTextContent(/isn't part of any organization/)
})

test('bad credentials say so', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(httpError(401))
  renderLogin()
  await submit()
  expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password.')
})

test('an unreachable backend is reported as such', async () => {
  vi.spyOn(api, 'post').mockRejectedValue(networkError())
  renderLogin()
  await submit()
  expect(await screen.findByRole('alert')).toHaveTextContent(/Can't reach the server/)
})

test('the email is prefilled after accepting an invitation', () => {
  renderLogin('/login?email=new%40acme.test')
  expect(screen.getByLabelText('Email')).toHaveValue('new@acme.test')
})
