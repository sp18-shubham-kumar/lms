/**
 * Axios API client for the DRF backend.
 *
 * Responsibilities:
 * - Base URL from VITE_API_URL.
 * - Attach the JWT access token and the active tenant header to every request.
 * - Transparently refresh the access token on a 401 and retry once.
 *
 * Token + tenant storage lives in `src/lib/auth.tsx` / `src/lib/tenant.tsx`;
 * this module reads them through small accessor hooks to avoid a circular import.
 */
import axios, { type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

export const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000/api'

// --- Token storage (module-level; kept in localStorage for the SPA) ---------
const ACCESS_KEY = 'lms.access'
const REFRESH_KEY = 'lms.refresh'
const TENANT_KEY = 'lms.tenant'
// Display details (name, accent) of the active tenant, so a hard refresh keeps the
// top bar and theme instead of showing "No tenant selected".
const TENANT_PROFILE_KEY = 'lms.tenantProfile'

export const tokenStore = {
  getAccess: () => localStorage.getItem(ACCESS_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh?: string) => {
    localStorage.setItem(ACCESS_KEY, access)
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

export const tenantStore = {
  get: () => localStorage.getItem(TENANT_KEY),
  set: (tenantId: string) => localStorage.setItem(TENANT_KEY, tenantId),
  getProfile: () => localStorage.getItem(TENANT_PROFILE_KEY),
  setProfile: (profile: string) => localStorage.setItem(TENANT_PROFILE_KEY, profile),
  clear: () => {
    localStorage.removeItem(TENANT_KEY)
    localStorage.removeItem(TENANT_PROFILE_KEY)
  },
}

export const api: AxiosInstance = axios.create({
  baseURL: API_URL,
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth + tenant on the way out.
api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = tokenStore.getAccess()
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  const tenant = tenantStore.get()
  if (tenant) config.headers.set('X-Tenant-Id', tenant)
  return config
})

// Refresh-on-401, retry once.
let refreshing: Promise<string | null> | null = null

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStore.getRefresh()
  if (!refresh) return null
  try {
    const resp = await axios.post(`${API_URL}/auth/token/refresh/`, { refresh })
    const access = resp.data.access as string
    tokenStore.set(access)
    return access
  } catch {
    tokenStore.clear()
    return null
  }
}

api.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const original = error.config as InternalAxiosRequestConfig & {
      _retried?: boolean
    }
    if (error.response?.status === 401 && original && !original._retried) {
      original._retried = true
      refreshing = refreshing ?? refreshAccessToken()
      const access = await refreshing
      refreshing = null
      if (access) {
        original.headers.set('Authorization', `Bearer ${access}`)
        return api(original)
      }
    }
    return Promise.reject(error)
  },
)
