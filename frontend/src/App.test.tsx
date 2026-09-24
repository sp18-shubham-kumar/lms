import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it } from 'vitest'

import App from './App'

describe('App', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('redirects an unauthenticated visitor to the sign-in screen', async () => {
    render(<App />)
    // ProtectedRoute sends "/" to "/login"; the login form should be present.
    expect(await screen.findByRole('heading', { name: /sign in/i })).toBeInTheDocument()
  })
})
