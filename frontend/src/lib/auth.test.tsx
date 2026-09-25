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
