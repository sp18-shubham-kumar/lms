import { Link, useNavigate } from 'react-router-dom'

import { AuthCard } from '../components/AuthCard'
import { useAuth, type Membership } from '../lib/auth'
import { useEnterTenant } from '../lib/useEnterTenant'

export function ChooseTenantPage() {
  const { session } = useAuth()
  const enterTenant = useEnterTenant()
  const navigate = useNavigate()
  const memberships = session?.memberships ?? []

  const pick = async (m: Membership) => {
    await enterTenant(m)
    navigate('/')
  }

  return (
    <AuthCard
      title="Choose an organization"
      subtitle={
        memberships.length > 0
          ? 'Pick which organization to work in.'
          : "You aren't a member of any organization yet."
      }
    >
      <ul className="space-y-2">
        {memberships.map((m) => (
          <li key={m.tenant_id}>
            <button
              onClick={() => void pick(m)}
              className="flex w-full items-center gap-3 rounded-lg border border-brand-100 px-4 py-3 text-left hover:bg-brand-50"
            >
              <span
                className="inline-block h-8 w-8 rounded"
                style={{ backgroundColor: m.accent_color || 'var(--tenant-accent)' }}
              />
              <span className="font-medium text-ink">{m.name}</span>
            </button>
          </li>
        ))}
      </ul>
      {session?.isPlatformOperator && (
        <Link
          to="/platform"
          className="block rounded-lg border border-brand-200 px-4 py-3 text-sm font-semibold text-brand-700 hover:bg-brand-50"
        >
          Platform console: create and manage organizations →
        </Link>
      )}
    </AuthCard>
  )
}
