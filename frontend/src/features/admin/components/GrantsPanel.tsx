/**
 * Grants tab: pick a person, see the roles they hold, grant or revoke one.
 *
 * Grants are listed per person (``?principal_id=``) so the panel stays small no
 * matter how many grants the tenant holds.
 */
import { useMemo, useState } from 'react'

import { useAuth } from '../../../lib/auth'
import { apiErrorMessage } from '../../../lib/errors'
import { usePeople } from '../../people/usePeople'
import { useOrgUnits } from '../../team/api'
import { useCreateGrant, useGrants, useRevokeGrant, useRoles } from '../api'
import type { GrantScopeType } from '../types'
import { ConfirmButton } from './ConfirmButton'
import { CARD, FIELD, PRIMARY_BUTTON, PRIMARY_STYLE } from './styles'

const PICKER_PAGE_SIZE = 200

interface GrantsPanelProps {
  personId: string | null
  onPersonChange: (personId: string | null) => void
}

export function GrantsPanel({ personId, onPersonChange }: GrantsPanelProps) {
  const { hasCapability } = useAuth()
  const people = usePeople(1, {}, PICKER_PAGE_SIZE)
  const roles = useRoles()
  const orgUnits = useOrgUnits()
  const grants = useGrants(personId)
  const createGrant = useCreateGrant()
  const revokeGrant = useRevokeGrant()

  const [roleId, setRoleId] = useState('')
  const [scopeType, setScopeType] = useState<GrantScopeType>('')
  const [scopeId, setScopeId] = useState('')

  const orgUnitNames = useMemo(
    () => new Map((orgUnits.data ?? []).map((u) => [u.id, u.name])),
    [orgUnits.data],
  )
  const canRevoke = hasCapability('member.offboard')
  const canSubmit = Boolean(personId && roleId && (scopeType === '' || scopeId))

  const submit = () => {
    if (!personId) return
    createGrant.mutate(
      {
        principal_id: personId,
        role: roleId,
        scope_type: scopeType,
        scope_id: scopeType === 'org_unit' ? scopeId : null,
      },
      {
        onSuccess: () => {
          setRoleId('')
          setScopeType('')
          setScopeId('')
        },
      },
    )
  }

  return (
    <div className="space-y-3">
      <label className="block text-[12.5px] text-ink-soft">
        Person
        <select
          value={personId ?? ''}
          onChange={(e) => {
            createGrant.reset()
            revokeGrant.reset()
            onPersonChange(e.target.value || null)
          }}
          className={`${FIELD} mt-1 block w-full`}
        >
          <option value="">Choose a person…</option>
          {(people.data?.results ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.display_name} ({p.email})
            </option>
          ))}
        </select>
      </label>
      {people.isError && (
        <p className="text-[12.5px] text-red-600">
          Couldn’t load people. {apiErrorMessage(people.error)}
        </p>
      )}

      {personId && (
        <>
          <div className={CARD}>
            <h3 className="text-sm font-semibold text-ink">Current roles</h3>
            {grants.isLoading ? (
              <p className="mt-2 text-ink-soft">Loading grants…</p>
            ) : grants.isError ? (
              <p className="mt-2 text-ink-soft">
                Couldn’t load grants. {apiErrorMessage(grants.error)}
              </p>
            ) : (grants.data ?? []).length === 0 ? (
              <p className="mt-2 text-[12.5px] text-ink-soft">No roles granted.</p>
            ) : (
              <ul className="mt-2 divide-y divide-brand-50">
                {(grants.data ?? []).map((g) => (
                  <li key={g.id} className="flex items-center justify-between py-2 text-[13px]">
                    <span>
                      <span className="font-semibold text-ink">{g.role_name}</span>{' '}
                      <span className="text-ink-soft">
                        {g.scope_type === 'org_unit'
                          ? `· ${orgUnitNames.get(g.scope_id ?? '') ?? 'Org unit'}`
                          : '· Tenant-wide'}
                      </span>
                    </span>
                    {canRevoke && (
                      <ConfirmButton
                        label="Revoke"
                        confirmLabel={`Revoke ${g.role_name}?`}
                        disabled={revokeGrant.isPending}
                        onConfirm={() => revokeGrant.mutate(g)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            )}
            {revokeGrant.isError && (
              <p className="mt-2 text-[12.5px] text-red-600">
                {apiErrorMessage(revokeGrant.error)}
              </p>
            )}
          </div>

          <form
            className={`${CARD} space-y-3`}
            onSubmit={(e) => {
              e.preventDefault()
              submit()
            }}
          >
            <h3 className="text-sm font-semibold text-ink">Grant a role</h3>
            <div className="grid gap-2 sm:grid-cols-3">
              <label className="text-[12.5px] text-ink-soft">
                Role
                <select
                  value={roleId}
                  onChange={(e) => setRoleId(e.target.value)}
                  className={`${FIELD} mt-1 block w-full`}
                >
                  <option value="">Choose a role…</option>
                  {(roles.data ?? []).map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-[12.5px] text-ink-soft">
                Scope
                <select
                  value={scopeType}
                  onChange={(e) => {
                    setScopeType(e.target.value as GrantScopeType)
                    setScopeId('')
                  }}
                  className={`${FIELD} mt-1 block w-full`}
                >
                  <option value="">Tenant-wide</option>
                  <option value="org_unit">One org unit</option>
                </select>
              </label>
              <label className="text-[12.5px] text-ink-soft">
                Org unit
                <select
                  value={scopeId}
                  disabled={scopeType !== 'org_unit'}
                  onChange={(e) => setScopeId(e.target.value)}
                  className={`${FIELD} mt-1 block w-full`}
                >
                  <option value="">Choose an org unit…</option>
                  {(orgUnits.data ?? []).map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.path}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <p className="text-[12px] text-ink-soft">
              An org-unit scope is recorded on the grant, but capability checks are tenant-wide
              today.
            </p>
            {createGrant.isError && (
              <p className="text-[12.5px] text-red-600">{apiErrorMessage(createGrant.error)}</p>
            )}
            <button
              type="submit"
              disabled={!canSubmit || createGrant.isPending}
              className={PRIMARY_BUTTON}
              style={PRIMARY_STYLE}
            >
              Grant role
            </button>
          </form>
        </>
      )}
    </div>
  )
}
