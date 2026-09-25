/** Redirects unauthenticated users to /login. */
import { Navigate, Outlet } from 'react-router-dom'

import { useAuth } from '../lib/auth'

export function ProtectedRoute() {
  const { isAuthenticated, bootstrapping } = useAuth()
  if (bootstrapping) return <div className="p-6 text-slate-500">Loading…</div>
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}
