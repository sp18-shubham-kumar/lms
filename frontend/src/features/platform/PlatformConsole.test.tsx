import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { httpError } from '../../test/http'
import { PlatformConsole } from './PlatformConsole'
import { slugify } from './slug'

const TENANT = {
  id: 't1',
  name: 'Acme Data',
  slug: 'acme',
  status: 'active',
  accent_color: '#0d9488',
  created_at: '2026-10-01T00:00:00Z',
  member_count: 3,
}

function renderConsole() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <PlatformConsole />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  vi.spyOn(api, 'get').mockResolvedValue({ data: [TENANT] } as never)
})
afterEach(() => vi.restoreAllMocks())

test('slugify matches what the backend slug field accepts', () => {
  expect(slugify('  Acme Data, Inc. ')).toBe('acme-data-inc')
  expect(slugify('x'.repeat(80))).toHaveLength(50)
})

test('lists organizations with their member counts', async () => {
  renderConsole()
  expect(await screen.findByText('Acme Data')).toBeInTheDocument()
  expect(screen.getByText('3')).toBeInTheDocument()
})

test('creates an organization and shows the admin accept link once', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: {
      tenant: { id: 't2', name: 'Globex Corp', slug: 'globex-corp' },
      admin: { id: 'p1', email: 'admin@globex.test', display_name: '' },
      role: 'Tenant Admin',
      invitation: {
        id: 'i1',
        email: 'admin@globex.test',
        role: 'Tenant Admin',
        role_id: 'r1',
        status: 'pending',
        expires_at: '2026-10-10T00:00:00Z',
        token: 'tok',
        invite_url: 'http://localhost:5173/invite/accept?token=tok',
      },
    },
  } as never)
  const user = userEvent.setup()
  renderConsole()

  await user.type(screen.getByLabelText('Name'), 'Globex Corp')
  expect(screen.getByLabelText('Slug')).toHaveValue('globex-corp')
  await user.type(screen.getByLabelText("First admin's email"), 'admin@globex.test')
  await user.click(screen.getByRole('button', { name: 'Create organization' }))

  expect(await screen.findByLabelText('Admin accept link')).toHaveValue(
    'http://localhost:5173/invite/accept?token=tok',
  )
  expect(post).toHaveBeenCalledWith('/platform/tenants/', {
    name: 'Globex Corp',
    slug: 'globex-corp',
    admin_email: 'admin@globex.test',
  })
})

test('an edited slug is kept and server errors are shown', async () => {
  const post = vi
    .spyOn(api, 'post')
    .mockRejectedValue(httpError(400, { detail: 'That slug is already taken.' }))
  const user = userEvent.setup()
  renderConsole()

  await user.type(screen.getByLabelText('Name'), 'Acme Data')
  const slug = screen.getByLabelText('Slug')
  await user.clear(slug)
  await user.type(slug, 'acme')
  await user.type(screen.getByLabelText("First admin's email"), 'a@acme.test')
  await user.click(screen.getByRole('button', { name: 'Create organization' }))

  expect(await screen.findByRole('alert')).toHaveTextContent('That slug is already taken.')
  expect(post).toHaveBeenCalledWith('/platform/tenants/', expect.objectContaining({ slug: 'acme' }))
})
