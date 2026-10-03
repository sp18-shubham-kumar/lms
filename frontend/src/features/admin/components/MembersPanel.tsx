/**
 * Members tab: find a member, open their profile, manage their access, or
 * offboard them. Offboarding ends the membership and revokes every grant, so it
 * needs member.offboard and an explicit confirm, and is never offered on yourself.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useAuth } from '../../../lib/auth'
import { apiErrorMessage } from '../../../lib/apiError'
import { useDebounced } from '../../../lib/useDebounced'
import { usePeople } from '../../people/usePeople'
import { usePersonProfile } from '../../people/usePersonProfile'
import { useOffboardMember } from '../api'
import { ConfirmButton } from './ConfirmButton'
import { CARD, FIELD, SECONDARY_BUTTON } from './styles'

interface MembersPanelProps {
  onManageAccess: (personId: string) => void
}

export function MembersPanel({ onManageAccess }: MembersPanelProps) {
  const { hasCapability } = useAuth()
  const me = usePersonProfile('me')
  const [q, setQ] = useState('')
  const [page, setPage] = useState(1)
  const search = useDebounced(q)
  const people = usePeople(page, { q: search })
  const offboard = useOffboardMember()

  const canOffboard = hasCapability('member.offboard')
  const canGrant = hasCapability('member.invite')
  const rows = people.data?.results ?? []
  const hasNext = Boolean(people.data?.next)

  return (
    <div className="space-y-3">
      <input
        aria-label="Search members"
        placeholder="Search by name or email"
        value={q}
        onChange={(e) => {
          setQ(e.target.value)
          setPage(1)
        }}
        className={`${FIELD} w-full`}
      />
      {offboard.isError && (
        <p className="text-[12.5px] text-red-600">{apiErrorMessage(offboard.error)}</p>
      )}
      {people.isLoading ? (
        <p className="text-ink-soft">Loading members…</p>
      ) : people.isError ? (
        <p className="text-ink-soft">Couldn’t load members. {apiErrorMessage(people.error)}</p>
      ) : rows.length === 0 ? (
        <p className="text-ink-soft">No members match.</p>
      ) : (
        <ul className={`${CARD} divide-y divide-brand-50 p-0`}>
          {rows.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-2 px-4 py-2.5">
              <Link to={`/people/${p.id}`} className="min-w-0">
                <span className="block truncate font-semibold text-ink">{p.display_name}</span>
                <span className="block truncate text-[12px] text-ink-soft">{p.email}</span>
              </Link>
              <span className="flex shrink-0 gap-2">
                {canGrant && (
                  <button className={SECONDARY_BUTTON} onClick={() => onManageAccess(p.id)}>
                    Manage access
                  </button>
                )}
                {canOffboard && p.id !== me.data?.id && (
                  <ConfirmButton
                    label="Offboard"
                    confirmLabel={`Offboard ${p.display_name}?`}
                    disabled={offboard.isPending}
                    onConfirm={() => offboard.mutate(p.id)}
                  />
                )}
              </span>
            </li>
          ))}
        </ul>
      )}
      {(page > 1 || hasNext) && (
        <div className="flex gap-2">
          <button
            className={SECONDARY_BUTTON}
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </button>
          <button
            className={SECONDARY_BUTTON}
            disabled={!hasNext}
            onClick={() => setPage(page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  )
}
