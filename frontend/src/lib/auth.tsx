import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

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
  bootstrapping: boolean
  session: Session | null
  login: (email: string, password: string) => Promise<Membership[]>
  loadSession: () => Promise<void>
  logout: () => void
  hasCapability: (capability: string) => boolean
  /**
   * Dev-only: seed a mock learner session so the UI is viewable without a
   * running backend. Surfaced behind an `import.meta.env.DEV` gate in the UI
   * (LoginPage). Remove once the real login flow is wired end-to-end.
   */
  enterDemo: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const hasTokenAtMount = Boolean(tokenStore.getAccess() && tenantStore.get())
  const [session, setSession] = useState<Session | null>(
    tokenStore.getAccess() ? { capabilities: [] } : null,
  )
  const [bootstrapping, setBootstrapping] = useState(hasTokenAtMount)

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

  // Dev-only demo session. No tokens, no network — just enough capabilities to
  // render the learner-facing screens (My path, Skills, Directory).
  const enterDemo = useCallback(() => {
    setSession({
      capabilities: ['directory.view', 'skill.claim.submit'],
      displayName: 'Priya Nair',
    })
  }, [])

  // Hydrate capabilities on app mount when a token + tenant are already persisted
  // (hard refresh / new tab). Must run exactly once; failure clears the session so
  // ProtectedRoute redirects to /login. We cannot call useNavigate here because
  // AuthProvider sits outside the Router.
  useEffect(() => {
    if (!hasTokenAtMount) return
    loadSession().catch(() => logout()).finally(() => setBootstrapping(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const hasCapability = useCallback(
    (capability: string) => session?.capabilities.includes(capability) ?? false,
    [session],
  )

  const value = useMemo<AuthContextValue>(
    () => ({
      isAuthenticated: session !== null,
      bootstrapping,
      session,
      login,
      loadSession,
      logout,
      hasCapability,
      enterDemo,
    }),
    [session, bootstrapping, login, loadSession, logout, hasCapability, enterDemo],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
