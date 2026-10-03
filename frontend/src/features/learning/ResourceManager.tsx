/**
 * Resource admin for resource.edit holders: every resource in the tenant
 * (including drafts and archived), create, edit, and archive. Archiving never
 * deletes — learner progress keeps pointing at the resource.
 */
import { useState } from 'react'

import { useAuth } from '../../lib/auth'
import { useSkills } from '../skills/api'
import { useArchiveResource, useCreateResource, useResources, useUpdateResource } from './api'
import { LearningTabs } from './components/LearningTabs'
import { ResourceForm } from './components/ResourceForm'
import { apiErrorMessage, resourceMeta } from './format'
import { RESOURCE_STATUSES, type LearningResource, type ResourceInput } from './types'

type Editing = { mode: 'new' } | { mode: 'edit'; resource: LearningResource } | null

export function ResourceManager() {
  const { hasCapability } = useAuth()
  const canEdit = hasCapability('resource.edit')

  const [status, setStatus] = useState('')
  const [editing, setEditing] = useState<Editing>(null)
  const resources = useResources({ status }, canEdit)
  const skills = useSkills()
  const create = useCreateResource()
  const update = useUpdateResource()
  const archive = useArchiveResource()

  if (!canEdit) {
    return (
      <section className="mx-auto max-w-3xl">
        <LearningTabs />
        <p className="mt-6 text-sm text-ink-soft">
          You don’t have permission to manage learning resources.
        </p>
      </section>
    )
  }

  const open = (next: Editing) => {
    create.reset()
    update.reset()
    setEditing(next)
  }
  const save = (input: ResourceInput) => {
    const close = { onSuccess: () => setEditing(null) }
    if (editing?.mode === 'edit') update.mutate({ id: editing.resource.id, ...input }, close)
    else create.mutate(input, close)
  }
  const saving = create.isPending || update.isPending
  const saveError = create.error ?? update.error

  return (
    <section className="mx-auto max-w-3xl">
      <LearningTabs />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <label className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft">
          Status
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="ml-2 rounded-md border border-brand-100 bg-white px-2 py-1 text-sm font-normal normal-case tracking-normal text-ink"
          >
            <option value="">All statuses</option>
            {RESOURCE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        {!editing && (
          <button
            type="button"
            onClick={() => open({ mode: 'new' })}
            className="rounded-lg px-3.5 py-1.5 text-[13px] font-semibold text-white"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            New resource
          </button>
        )}
      </div>

      {editing && (
        <div className="mt-4">
          <ResourceForm
            key={editing.mode === 'edit' ? editing.resource.id : 'new'}
            initial={editing.mode === 'edit' ? editing.resource : undefined}
            skills={skills.data ?? []}
            busy={saving}
            error={saveError ? apiErrorMessage(saveError) : null}
            onSubmit={save}
            onCancel={() => setEditing(null)}
          />
        </div>
      )}

      {resources.isLoading && <p className="mt-4 text-ink-soft">Loading resources…</p>}
      <ul className="mt-4 divide-y divide-brand-100 rounded-xl border border-brand-100 bg-white">
        {(resources.data ?? []).map((r) => (
          <li key={r.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
            <div className="min-w-0 flex-1">
              <div className="truncate font-semibold text-ink">{r.title}</div>
              <div className="text-[11.5px] text-ink-soft">
                {resourceMeta(r)}
                {r.skills.length > 0 &&
                  ` · ${r.skills.map((s) => `${s.skill_name} L${s.level}`).join(', ')}`}
              </div>
            </div>
            <span className="font-mono text-[10px] uppercase tracking-wide text-ink-soft">
              {r.status}
            </span>
            <button
              type="button"
              onClick={() => open({ mode: 'edit', resource: r })}
              className="text-[12px] font-semibold"
              style={{ color: 'var(--tenant-accent)' }}
            >
              Edit
            </button>
            {r.status !== 'archived' && (
              <button
                type="button"
                disabled={archive.isPending}
                onClick={() => {
                  if (window.confirm(`Archive “${r.title}”? Learners will no longer see it.`))
                    archive.mutate(r.id)
                }}
                className="text-[12px] text-ink-soft hover:text-ink"
              >
                Archive
              </button>
            )}
          </li>
        ))}
        {resources.data?.length === 0 && (
          <li className="px-4 py-3 text-sm text-ink-soft">No resources yet.</li>
        )}
      </ul>
    </section>
  )
}
