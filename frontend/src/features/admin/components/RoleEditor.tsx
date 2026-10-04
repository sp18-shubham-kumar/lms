/** Name + capability checklist for creating or editing a role. */
import { useState } from 'react'

import type { Role, RoleInput } from '../types'
import { CARD, FIELD, PRIMARY_BUTTON, PRIMARY_STYLE, SECONDARY_BUTTON } from './styles'

interface RoleEditorProps {
  role?: Role
  capabilities: string[]
  busy: boolean
  error?: string
  onSave: (input: RoleInput) => void
  onCancel: () => void
}

export function RoleEditor({ role, capabilities, busy, error, onSave, onCancel }: RoleEditorProps) {
  const [name, setName] = useState(role?.name ?? '')
  const [selected, setSelected] = useState<Set<string>>(new Set(role?.capabilities ?? []))

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key)
      else next.add(key)
      return next
    })

  return (
    <form
      className={`${CARD} space-y-3`}
      onSubmit={(e) => {
        e.preventDefault()
        onSave({ name: name.trim(), capabilities: [...selected].sort() })
      }}
    >
      <h3 className="text-sm font-semibold text-ink">{role ? `Edit ${role.name}` : 'New role'}</h3>
      <label className="block text-[12.5px] text-ink-soft">
        Name
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
          className={`${FIELD} mt-1 block w-full`}
        />
      </label>
      <fieldset>
        <legend className="text-[12.5px] text-ink-soft">Capabilities</legend>
        <div className="mt-1 grid gap-1 sm:grid-cols-2">
          {capabilities.map((key) => (
            <label key={key} className="flex items-center gap-2 font-mono text-[12px] text-ink">
              <input type="checkbox" checked={selected.has(key)} onChange={() => toggle(key)} />
              {key}
            </label>
          ))}
        </div>
      </fieldset>
      {error && <p className="text-[12.5px] text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className={PRIMARY_BUTTON}
          style={PRIMARY_STYLE}
        >
          {role ? 'Save role' : 'Create role'}
        </button>
        <button type="button" onClick={onCancel} className={SECONDARY_BUTTON}>
          Cancel
        </button>
      </div>
    </form>
  )
}
