import { useNavigate } from 'react-router-dom'

import { useTenant, type Tenant } from '../lib/tenant'

// Placeholder tenants. Phase 1 replaces this with the memberships returned by the
// session endpoint (login lists a person's active memberships; one → straight in,
// two+ → this picker).
const DEMO_TENANTS: Tenant[] = [
  { id: '00000000-0000-0000-0000-000000000001', name: 'Acme', accentColor: '#4f46e5' },
  { id: '00000000-0000-0000-0000-000000000002', name: 'Northwind', accentColor: '#0891b2' },
]

export function ChooseTenantPage() {
  const { setTenant } = useTenant()
  const navigate = useNavigate()

  const pick = (tenant: Tenant) => {
    setTenant(tenant) // clears cross-tenant cache + applies theme
    navigate('/')
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <div className="w-full max-w-md space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-xl font-semibold text-slate-900">Choose an organization</h1>
        <p className="text-sm text-slate-500">
          You have access to more than one tenant. Pick which one to work in.
        </p>
        <ul className="space-y-2">
          {DEMO_TENANTS.map((tenant) => (
            <li key={tenant.id}>
              <button
                onClick={() => pick(tenant)}
                className="flex w-full items-center gap-3 rounded-lg border border-slate-200 px-4 py-3 text-left hover:bg-slate-50"
              >
                <span
                  className="inline-block h-8 w-8 rounded"
                  style={{ backgroundColor: tenant.accentColor }}
                />
                <span className="font-medium text-slate-800">{tenant.name}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
