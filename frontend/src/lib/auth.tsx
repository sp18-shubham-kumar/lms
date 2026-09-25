import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

import { api, tenantStore, tokenStore } from './api'

export interface Membership {
  tenant_id: string
  slug: string
  name: string
  accent_color: string
}

export interface Session {
  /** Capability keys the current user holds in the active tenant. */
  capabilities: string[]
  /** Display name of the signed-in person. */
  displayName?: string
}

interface AuthContextValue {
  isAuthenticated: boolean
  session: Session | null
  login: (email: string, password: string) => Promise<Membership[]>
  loadSession: () => Promise<void>
  logout: () => void
  hasCapability: (capability: string) => boolean
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(
    tokenStore.getAccess() ? { capabilities: [] } : null,
  )

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.post('/auth/login/', { email, password })
    tokenStore.set(resp.data.access, resp.data.refresh)
    setSession({ capabilities: [] })
    return resp.data.memberships as Membership[]
  }, [])

  const loadSession = useCallback(async () => {
    if (!tokenStore.getAccess() || !tenantStore.get()) return
    const resp = await api.get('/auth/session/')
    setSession({
      capabilities: resp.data.capabilities ?? [],
      displayName: resp.data.person?.display_name,
    })
  }, [])

  const logout = useCallback(() => {
    tokenStore.clear()
    tenantStore.clear()
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
      loadSession,
      logout,
      hasCapability,
    }),
    [session, login, loadSession, logout, hasCapability],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
