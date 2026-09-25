import { useLocation, useNavigate } from 'react-router-dom'

import { useAuth, type Membership } from '../lib/auth'
import { useTenant } from '../lib/tenant'

export function ChooseTenantPage() {
  const { setTenant } = useTenant()
  const { loadSession } = useAuth()
  const navigate = useNavigate()
  const memberships = (useLocation().state?.memberships ?? []) as Membership[]

  const pick = async (m: Membership) => {
    setTenant({ id: m.tenant_id, name: m.name, accentColor: m.accent_color })
    await loadSession()
    navigate('/')
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Choose an organization</h1>
        <p className="text-sm text-slate-500">
          You belong to more than one. Pick which to work in.
        </p>
        <ul className="space-y-2">
          {memberships.map((m) => (
            <li key={m.tenant_id}>
              <button
                onClick={() => void pick(m)}
                className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50"
              >
                <span
                  className="inline-block h-8 w-8 rounded"
                  style={{ backgroundColor: m.accent_color }}
                />
                <span className="font-medium text-slate-800">{m.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
