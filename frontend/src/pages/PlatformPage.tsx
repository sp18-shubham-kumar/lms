/**
 * Platform operator area. Outside the tenant AppShell: it acts across tenants,
 * so there is no active tenant here and no tenant name in the top bar.
 */
import { Link, Navigate, useNavigate } from 'react-router-dom'

import { PlatformConsole } from '../features/platform/PlatformConsole'
import { useAuth } from '../lib/auth'

export function PlatformPage() {
  const { session, logout } = useAuth()
  const navigate = useNavigate()

  if (!session?.isPlatformOperator) return <Navigate to="/" replace />

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-full flex-col">
      <header
        className="flex items-center justify-between border-b border-brand-100 bg-white px-6 py-3"
        style={{ borderTopColor: 'var(--tenant-accent)', borderTopWidth: 3 }}
      >
        <div className="flex items-center gap-3">
          <span
            className="inline-block h-6 w-6 rounded"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          />
          <span className="font-semibold text-ink">Skills LMS</span>
          <span className="text-brand-200">/</span>
          <span className="text-ink-soft">Platform</span>
        </div>
        <div className="flex items-center gap-4">
          {session.memberships.length > 0 && (
            <Link to="/choose" className="text-sm font-medium text-brand-700 hover:underline">
              My organizations
            </Link>
          )}
          <span className="text-sm text-ink-soft">{session.displayName ?? 'Operator'}</span>
          <button
            onClick={handleLogout}
            className="rounded-md border border-brand-100 px-3 py-1 text-sm text-ink-soft hover:bg-brand-50"
          >
            Sign out
          </button>
        </div>
      </header>
      <main className="flex-1 overflow-auto p-8">
        <PlatformConsole />
      </main>
    </div>
  )
}
