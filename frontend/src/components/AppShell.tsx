/**
 * The one shell. Not three apps — a single navigation where sections appear
 * according to the user's capabilities (spec: Frontend architecture).
 *
 * The tenant name is pinned in the top bar permanently.
 */
import { NavLink, Outlet, useNavigate } from 'react-router-dom'

import { useAuth } from '../lib/auth'
import { useTenant } from '../lib/tenant'

interface NavItem {
  to: string
  label: string
  /** If set, the item only renders when the user holds this capability. */
  capability?: string
}

// Ungated items are available to any signed-in member; gated items appear only
// when the capability is present in the session payload.
const NAV_ITEMS: NavItem[] = [
  { to: '/', label: 'My path' },
  { to: '/skills', label: 'Skills', capability: 'skill.claim.submit' },
  { to: '/directory', label: 'Directory', capability: 'directory.view' },
  { to: '/team', label: 'Team', capability: 'report.org.view' },
  { to: '/career-paths', label: 'Career paths', capability: 'jobprofile.edit' },
  { to: '/admin', label: 'Admin', capability: 'member.invite' },
]

export function AppShell() {
  const { session, logout, hasCapability } = useAuth()
  const { tenant } = useTenant()
  const navigate = useNavigate()

  const visibleItems = NAV_ITEMS.filter(
    (item) => !item.capability || hasCapability(item.capability),
  )

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
          {tenant?.logoUrl ? (
            <img src={tenant.logoUrl} alt="" className="h-6 w-6 rounded" />
          ) : (
            <span
              className="inline-block h-6 w-6 rounded"
              style={{ backgroundColor: 'var(--tenant-accent)' }}
            />
          )}
          <span className="font-semibold text-ink">Skills LMS</span>
          {/* Tenant name is always visible. */}
          <span className="text-brand-200">/</span>
          <span className="text-ink-soft">{tenant?.name ?? 'No tenant selected'}</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-ink-soft">{session?.displayName ?? 'Signed in'}</span>
          <button
            onClick={handleLogout}
            className="rounded-md border border-brand-100 px-3 py-1 text-sm text-ink-soft hover:bg-brand-50"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <nav className="w-52 shrink-0 border-r border-brand-100 bg-white p-3">
          <ul className="space-y-1">
            {visibleItems.map((item) => (
              <li key={item.to}>
                <NavLink
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    `block rounded-lg px-3 py-2 text-sm ${
                      isActive ? 'font-medium' : 'text-ink-soft hover:bg-brand-50'
                    }`
                  }
                  style={({ isActive }) =>
                    isActive
                      ? {
                          backgroundColor: 'color-mix(in srgb, var(--tenant-accent) 12%, white)',
                          color: 'color-mix(in srgb, var(--tenant-accent) 75%, black)',
                        }
                      : undefined
                  }
                >
                  {item.label}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <main className="flex-1 overflow-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
