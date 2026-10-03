/** Roles tab: each role's capability bundle, with create / edit / delete. */
import { useState } from 'react'

import { apiErrorMessage } from '../../../lib/errors'
import { useCapabilities, useDeleteRole, useRoles, useSaveRole } from '../api'
import type { Role } from '../types'
import { ConfirmButton } from './ConfirmButton'
import { RoleEditor } from './RoleEditor'
import { PRIMARY_BUTTON, PRIMARY_STYLE, SECONDARY_BUTTON } from './styles'

type Editing = { mode: 'new' } | { mode: 'edit'; role: Role } | null

export function RolesPanel() {
  const roles = useRoles()
  const capabilities = useCapabilities()
  const save = useSaveRole()
  const remove = useDeleteRole()
  const [editing, setEditing] = useState<Editing>(null)

  const close = () => {
    save.reset()
    setEditing(null)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-[12.5px] text-ink-soft">
          A role bundles capabilities. Grant roles to people on the Grants tab.
        </p>
        {!editing && (
          <button
            onClick={() => setEditing({ mode: 'new' })}
            className={PRIMARY_BUTTON}
            style={PRIMARY_STYLE}
          >
            New role
          </button>
        )}
      </div>

      {editing && (
        <RoleEditor
          key={editing.mode === 'edit' ? editing.role.id : 'new'}
          role={editing.mode === 'edit' ? editing.role : undefined}
          capabilities={capabilities.data ?? []}
          busy={save.isPending}
          error={save.isError ? apiErrorMessage(save.error) : undefined}
          onCancel={close}
          onSave={(input) =>
            save.mutate(
              { ...input, id: editing.mode === 'edit' ? editing.role.id : undefined },
              { onSuccess: close },
            )
          }
        />
      )}

      {remove.isError && (
        <p className="text-[12.5px] text-red-600">{apiErrorMessage(remove.error)}</p>
      )}

      {roles.isLoading ? (
        <p className="text-ink-soft">Loading roles…</p>
      ) : roles.isError ? (
        <p className="text-ink-soft">Couldn’t load roles. {apiErrorMessage(roles.error)}</p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {(roles.data ?? []).map((r) => (
            <div key={r.id} className="rounded-xl border border-brand-100 bg-white p-3.5">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-ink">{r.name}</span>
                {r.is_system && (
                  <span className="font-mono text-[9px] uppercase tracking-wide text-ink-soft">
                    system
                  </span>
                )}
              </div>
              <ul className="mt-2 space-y-0.5">
                {r.capabilities.length === 0 && (
                  <li className="text-[12px] text-ink-soft">No capabilities</li>
                )}
                {r.capabilities.map((c) => (
                  <li key={c} className="font-mono text-[10.5px] text-ink-soft">
                    {c}
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex gap-2">
                <button
                  onClick={() => {
                    save.reset()
                    setEditing({ mode: 'edit', role: r })
                  }}
                  className={SECONDARY_BUTTON}
                >
                  Edit
                </button>
                <ConfirmButton
                  label="Delete"
                  confirmLabel={`Delete ${r.name}?`}
                  disabled={remove.isPending}
                  onConfirm={() => remove.mutate(r.id)}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
