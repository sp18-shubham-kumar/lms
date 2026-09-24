/**
 * Authentication + session context.
 *
 * The spec's session payload carries the user, their capability set, the active
 * tenant theme, and org scope — one request drives all conditional rendering.
 * Phase 1 will add a `/auth/session/` (or `/me/`) endpoint returning that shape;
 * until then this provider tracks token presence and exposes a capability seam
 * (`hasCapability`) so components can be written against it now.
 */
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { api, tokenStore } from './api'

export interface Session {
  /** Capability keys the current user holds in the active tenant. */
  capabilities: string[]
  /** Display name of the signed-in person. */
  displayName?: string
}

interface AuthContextValue {
  isAuthenticated: boolean
  session: Session | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
  hasCapability: (capability: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(
    tokenStore.getAccess() ? { capabilities: [] } : null,
  )

  const login = useCallback(async (username: string, password: string) => {
    const resp = await api.post('/auth/token/', { username, password })
    tokenStore.set(resp.data.access, resp.data.refresh)
    // TODO(phase-1): fetch /auth/session/ and populate capabilities + theme.
    setSession({ capabilities: [] })
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    setSession(null)
  }, [])

  const hasCapability = useCallback(
    (capability: string) => session?.capabilities.includes(capability) ?? false,
    [session],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: session !== null,
      session,
      login,
      logout,
      hasCapability,
    }),
    [session, login, logout, hasCapability],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
