import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, expect, test, vi } from 'vitest'

import { api } from './api'
import { AuthProvider, useAuth } from './auth'

function Probe() {
  const { login, session } = useAuth()
  return (
    <div>
      <button onClick={() => void login('a@acme.test', 'pw')}>go</button>
      <span data-testid="caps">{session?.capabilities.join(',') ?? 'none'}</span>
    </div>
  )
}

beforeEach(() => localStorage.clear())

test('login stores tokens and returns memberships', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: {
      access: 'a',
      refresh: 'r',
      memberships: [{ tenant_id: 't1', slug: 's', name: 'N', accent_color: '#000' }],
    },
  } as never)
  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
  screen.getByText('go').click()
  await waitFor(() => expect(localStorage.getItem('lms.access')).toBe('a'))
  expect(post).toHaveBeenCalledWith('/auth/login/', { email: 'a@acme.test', password: 'pw' })
})

test('hydrates session on mount when a token + tenant exist', async () => {
  // Pre-seed storage so AuthProvider sees a token + tenant at mount time.
  localStorage.setItem('lms.access', 'stored-access-token')
  localStorage.setItem('lms.tenant', 'tenant-123')

  const get = vi.spyOn(api, 'get').mockResolvedValue({
    data: {
      capabilities: ['directory.view'],
      person: { display_name: 'A' },
    },
  } as never)

  render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )

  // Before hydration settles, capabilities are empty; after, they should be populated.
  await waitFor(() => expect(screen.getByTestId('caps').textContent).toContain('directory.view'))
  expect(get).toHaveBeenCalledWith('/auth/session/')
})
