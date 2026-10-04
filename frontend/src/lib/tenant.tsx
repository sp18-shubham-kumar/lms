/**
 * Active-tenant context + runtime theming.
 *
 * The tenant name must sit permanently in the top bar (people working across two
 * orgs must never be unsure which one they're acting in). The accent colour is
 * applied by writing a CSS custom property on :root, so branding changes without
 * a rebuild.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { resetForTenantSwitch } from './queryClient'
import { tenantStore } from './api'

export interface Tenant {
  id: string
  name: string
  accentColor?: string
  logoUrl?: string
}

interface TenantContextValue {
  tenant: Tenant | null
  /** Switch tenant: clears cross-tenant cache, persists the id, applies theme. */
  setTenant: (tenant: Tenant | null) => void
}

const TenantContext = createContext<TenantContextValue | null>(null)

function applyTheme(tenant: Tenant | null): void {
  // Defaults to the Path teal; a tenant's own accent still overrides it.
  const accent = tenant?.accentColor ?? '#0d9488'
  document.documentElement.style.setProperty('--tenant-accent', accent)
}

/** The persisted tenant, if its profile still matches the persisted tenant id. */
function restoreTenant(): Tenant | null {
  const id = tenantStore.get()
  const raw = tenantStore.getProfile()
  if (!id || !raw) return null
  try {
    const profile = JSON.parse(raw) as Tenant
    return profile.id === id ? profile : null
  } catch {
    return null
  }
}

export function TenantProvider({ children }: { children: ReactNode }) {
  const [tenant, setTenantState] = useState<Tenant | null>(restoreTenant)

  useEffect(() => {
    applyTheme(tenant)
  }, [tenant])

  const setTenant = useCallback((next: Tenant | null) => {
    // Never carry one tenant's cached data into another.
    resetForTenantSwitch()
    if (next) {
      tenantStore.set(next.id)
      tenantStore.setProfile(JSON.stringify(next))
    } else {
      tenantStore.clear()
    }
    setTenantState(next)
  }, [])

  const value = useMemo<TenantContextValue>(() => ({ tenant, setTenant }), [tenant, setTenant])

  return <TenantContext.Provider value={value}>{children}</TenantContext.Provider>
}

export function useTenant(): TenantContextValue {
  const ctx = useContext(TenantContext)
  if (!ctx) throw new Error('useTenant must be used within a TenantProvider')
  return ctx
}
