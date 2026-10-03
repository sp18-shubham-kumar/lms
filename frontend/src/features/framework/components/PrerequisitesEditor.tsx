/**
 * A skill's outgoing edges: prerequisites (must stay acyclic) and advisory
 * "adjacent" links. The backend rejects self-edges and cycles; its reason is
 * shown verbatim so the author knows which link to drop.
 */
import { useState } from 'react'

import { ConfirmAction } from '../../../components/ConfirmAction'
import { apiErrorMessage } from '../../../lib/apiError'
import type { ApiSkill } from '../../skills/types'
import { useAddEdge, useRemoveEdge, useSkillEdges } from '../api'
import type { EdgeKind } from '../types'

const KIND_LABEL: Record<EdgeKind, string> = {
  prerequisite: 'Requires',
  adjacent: 'Related to',
}

interface PrerequisitesEditorProps {
  skill: ApiSkill
  /** Every skill the tenant can see, used for names and the picker. */
  catalogue: ApiSkill[]
  editable: boolean
}

export function PrerequisitesEditor({ skill, catalogue, editable }: PrerequisitesEditorProps) {
  const edges = useSkillEdges(skill.id)
  const add = useAddEdge(skill.id)
  const remove = useRemoveEdge(skill.id)
  const [target, setTarget] = useState('')
  const [kind, setKind] = useState<EdgeKind>('prerequisite')

  const names = new Map(catalogue.map((s) => [s.id, s.name]))
  const linked = new Set((edges.data ?? []).map((e) => `${e.kind}:${e.to_skill}`))
  const options = catalogue
    .filter((s) => s.id !== skill.id && s.status !== 'retired')
    .sort((a, b) => a.name.localeCompare(b.name))

  const submit = () => {
    if (!target) return
    add.mutate({ to_skill: target, kind }, { onSuccess: () => setTarget('') })
  }

  if (edges.isLoading) return <p className="text-ink-soft">Loading links…</p>

  return (
    <div className="space-y-4">
      {(edges.data ?? []).length === 0 ? (
        <p className="text-[13px] text-ink-soft">No prerequisites or related skills yet.</p>
      ) : (
        <ul className="divide-y divide-brand-50 rounded-xl border border-brand-100 bg-white">
          {(edges.data ?? []).map((edge) => (
            <li key={edge.id} className="flex items-center justify-between gap-3 px-4 py-2.5">
              <span className="text-[13px] text-ink">
                <span className="font-mono text-[11px] uppercase tracking-wide text-ink-soft">
                  {KIND_LABEL[edge.kind]}
                </span>{' '}
                <span className="font-semibold">{names.get(edge.to_skill) ?? 'Unknown skill'}</span>
              </span>
              {editable && (
                <ConfirmAction
                  label="Remove"
                  prompt="Remove this link?"
                  confirmLabel="Remove"
                  tone="danger"
                  busy={remove.isPending}
                  onConfirm={() => remove.mutate(edge.id)}
                />
              )}
            </li>
          ))}
        </ul>
      )}

      {editable ? (
        <div className="rounded-xl border border-brand-100 bg-white p-4">
          <div className="text-[13px] font-semibold text-ink">Add a link</div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <select
              aria-label="Link type"
              value={kind}
              onChange={(e) => setKind(e.target.value as EdgeKind)}
              className="rounded-md border border-brand-100 bg-white px-2 py-1.5 text-[13px] text-ink"
            >
              <option value="prerequisite">Requires (prerequisite)</option>
              <option value="adjacent">Related to (adjacent)</option>
            </select>
            <select
              aria-label="Linked skill"
              value={target}
              onChange={(e) => setTarget(e.target.value)}
              className="min-w-56 rounded-md border border-brand-100 bg-white px-2 py-1.5 text-[13px] text-ink"
            >
              <option value="">Choose a skill…</option>
              {options.map((s) => (
                <option key={s.id} value={s.id} disabled={linked.has(`${kind}:${s.id}`)}>
                  {s.name}
                  {s.version > 1 ? ` (v${s.version})` : ''}
                </option>
              ))}
            </select>
            <button
              type="button"
              onClick={submit}
              disabled={!target || add.isPending}
              className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--tenant-accent)' }}
            >
              Add link
            </button>
          </div>
          {add.isError && (
            <p role="alert" className="mt-2 text-[12.5px] text-red-600">
              {apiErrorMessage(add.error, 'Could not add the link.')}
            </p>
          )}
        </div>
      ) : (
        <p className="text-[12.5px] text-ink-soft">
          Links on global skills are managed by the platform.
        </p>
      )}
    </div>
  )
}
