import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

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
  /** Organizations the person can act in. */
  memberships: Membership[]
  /** Platform operators can create tenants (the /platform screen). */
  isPlatformOperator: boolean
}

export interface LoginResult {
  memberships: Membership[]
  isPlatformOperator: boolean
}

/** Shape shared by /auth/login/, /auth/me/ and /auth/session/. */
interface AccountPayload {
  person?: { display_name?: string }
  capabilities?: string[]
  memberships?: Membership[]
  is_platform_operator?: boolean
}

function toSession(data: AccountPayload): Session {
  return {
    capabilities: data.capabilities ?? [],
    displayName: data.person?.display_name,
    memberships: data.memberships ?? [],
    isPlatformOperator: data.is_platform_operator ?? false,
  }
}

const EMPTY_SESSION: Session = { capabilities: [], memberships: [], isPlatformOperator: false }

interface AuthContextValue {
  isAuthenticated: boolean
  bootstrapping: boolean
  session: Session | null
  login: (email: string, password: string) => Promise<LoginResult>
  /** Load capabilities for the active tenant. No-op without a tenant. */
  loadSession: () => Promise<void>
  /** Load the account without a tenant (memberships + operator flag). */
  loadAccount: () => Promise<void>
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
  const hasTokenAtMount = Boolean(tokenStore.getAccess())
  const [session, setSession] = useState<Session | null>(hasTokenAtMount ? EMPTY_SESSION : null)
  const [bootstrapping, setBootstrapping] = useState(hasTokenAtMount)

  const login = useCallback(async (email: string, password: string) => {
    const resp = await api.post('/auth/login/', { email, password })
    tokenStore.set(resp.data.access, resp.data.refresh)
    const next = toSession(resp.data)
    setSession(next)
    return { memberships: next.memberships, isPlatformOperator: next.isPlatformOperator }
  }, [])

  const loadSession = useCallback(async () => {
    if (!tokenStore.getAccess() || !tenantStore.get()) return
    const resp = await api.get('/auth/session/')
    setSession(toSession(resp.data))
  }, [])

  const loadAccount = useCallback(async () => {
    if (!tokenStore.getAccess()) return
    const resp = await api.get('/auth/me/')
    setSession(toSession(resp.data))
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
      ...EMPTY_SESSION,
      capabilities: ['directory.view', 'skill.claim.submit'],
      displayName: 'Priya Nair',
    })
  }, [])

  // Hydrate on app mount when a token is already persisted (hard refresh / new
  // tab): the tenant session if a tenant is selected, otherwise the bare account
  // (a platform operator, or someone still choosing an organization). Must run
  // exactly once; failure clears the session so ProtectedRoute redirects to
  // /login. We cannot call useNavigate here because AuthProvider sits outside the
  // Router.
  useEffect(() => {
    if (!hasTokenAtMount) return
    const restore = tenantStore.get() ? loadSession : loadAccount
    restore()
      .catch(() => logout())
      .finally(() => setBootstrapping(false))
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
      loadAccount,
      logout,
      hasCapability,
      enterDemo,
    }),
    [session, bootstrapping, login, loadSession, loadAccount, logout, hasCapability, enterDemo],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
