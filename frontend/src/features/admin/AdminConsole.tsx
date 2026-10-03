/**
 * Admin console: a tab strip over the admin panels.
 *
 * Tabs are a plain array — add one by appending an entry. A tab with a
 * ``capability`` is only shown to callers who hold it (the backend still enforces
 * every call). ``render`` receives a small context so tabs can hand off to each
 * other, e.g. Members → "Manage access" opens Grants with that person selected.
 */
import { useState, type ReactNode } from 'react'

import { useAuth } from '../../lib/auth'
import { GrantsPanel } from './components/GrantsPanel'
import { ImportPanel } from './components/ImportPanel'
import { MembersPanel } from './components/MembersPanel'
import { RolesPanel } from './components/RolesPanel'

export interface AdminTabContext {
  /** Switch to another tab by id. */
  openTab: (id: string) => void
  /** Person preselected on the Grants tab. */
  grantsPersonId: string | null
  setGrantsPersonId: (personId: string | null) => void
}

export interface AdminTab {
  id: string
  label: string
  capability?: string
  render: (ctx: AdminTabContext) => ReactNode
}

export const ADMIN_TABS: AdminTab[] = [
  {
    id: 'members',
    label: 'Members',
    capability: 'directory.view',
    render: (ctx) => (
      <MembersPanel
        onManageAccess={(personId) => {
          ctx.setGrantsPersonId(personId)
          ctx.openTab('grants')
        }}
      />
    ),
  },
  { id: 'roles', label: 'Roles', capability: 'member.invite', render: () => <RolesPanel /> },
  {
    id: 'grants',
    label: 'Grants',
    capability: 'member.invite',
    render: (ctx) => (
      <GrantsPanel personId={ctx.grantsPersonId} onPersonChange={ctx.setGrantsPersonId} />
    ),
  },
  { id: 'import', label: 'Import', capability: 'member.invite', render: () => <ImportPanel /> },
]

export function AdminConsole({ tabs = ADMIN_TABS }: { tabs?: AdminTab[] }) {
  const { hasCapability } = useAuth()
  const visible = tabs.filter((t) => !t.capability || hasCapability(t.capability))
  const [activeId, setActiveId] = useState<string | null>(null)
  const [grantsPersonId, setGrantsPersonId] = useState<string | null>(null)

  const active = visible.find((t) => t.id === activeId) ?? visible[0]

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Admin</h1>
        <p className="mt-1 text-sm text-ink-soft">Members, roles, access and import.</p>
      </div>

      {visible.length === 0 ? (
        <p className="text-ink-soft">You don’t have access to any admin tools.</p>
      ) : (
        <>
          <div role="tablist" className="flex gap-1 border-b border-brand-100">
            {visible.map((t) => {
              const selected = t.id === active?.id
              return (
                <button
                  key={t.id}
                  role="tab"
                  aria-selected={selected}
                  onClick={() => setActiveId(t.id)}
                  className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold ${
                    selected
                      ? 'border-[var(--tenant-accent)] text-ink'
                      : 'border-transparent text-ink-soft hover:text-ink'
                  }`}
                >
                  {t.label}
                </button>
              )
            })}
          </div>
          <div role="tabpanel">
            {active?.render({ openTab: setActiveId, grantsPersonId, setGrantsPersonId })}
          </div>
        </>
      )}
    </section>
  )
}
