/**
 * Create/edit form for a learning resource, including the skills it teaches and
 * the level (1..5) it teaches each toward. Saving sends every skill link; the
 * backend replaces the resource's links with exactly this set.
 */
import { useState, type FormEvent } from 'react'

import type { ApiSkill } from '../../skills/types'
import {
  KIND_LABELS,
  RESOURCE_KINDS,
  RESOURCE_STATUSES,
  type LearningResource,
  type ResourceInput,
  type ResourceKind,
  type ResourceStatus,
} from '../types'

interface ResourceFormProps {
  initial?: LearningResource
  skills: ApiSkill[]
  busy: boolean
  error?: string | null
  onSubmit: (input: ResourceInput) => void
  onCancel: () => void
}

const LEVELS = [1, 2, 3, 4, 5]
const FIELD = 'mt-1 w-full rounded-md border border-brand-100 bg-white px-2 py-1.5 text-sm text-ink'
const LABEL = 'block text-[12px] font-medium text-ink-soft'

function toInput(resource?: LearningResource): ResourceInput {
  return {
    title: resource?.title ?? '',
    kind: resource?.kind ?? 'course',
    url: resource?.url ?? '',
    provider: resource?.provider ?? '',
    description: resource?.description ?? '',
    module_count: resource?.module_count ?? 1,
    duration_minutes: resource?.duration_minutes ?? null,
    status: resource?.status ?? 'draft',
    skills: (resource?.skills ?? []).map(({ skill, level }) => ({ skill, level })),
  }
}

export function ResourceForm({
  initial,
  skills,
  busy,
  error,
  onSubmit,
  onCancel,
}: ResourceFormProps) {
  const [form, setForm] = useState<ResourceInput>(() => toInput(initial))
  const set = <K extends keyof ResourceInput>(key: K, value: ResourceInput[K]) =>
    setForm((prev) => ({ ...prev, [key]: value }))

  const linked = new Set(form.skills.map((s) => s.skill))
  const unlinked = skills.filter((s) => !linked.has(s.id))

  const setLink = (index: number, patch: Partial<{ skill: string; level: number }>) =>
    set(
      'skills',
      form.skills.map((link, i) => (i === index ? { ...link, ...patch } : link)),
    )

  const submit = (event: FormEvent) => {
    event.preventDefault()
    onSubmit(form)
  }

  return (
    <form
      onSubmit={submit}
      aria-label={initial ? `Edit ${initial.title}` : 'New resource'}
      className="space-y-3 rounded-xl border border-brand-100 bg-white p-4"
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <label className={`${LABEL} sm:col-span-2`}>
          Title
          <input
            required
            value={form.title}
            onChange={(e) => set('title', e.target.value)}
            className={FIELD}
          />
        </label>
        <label className={LABEL}>
          Kind
          <select
            value={form.kind}
            onChange={(e) => set('kind', e.target.value as ResourceKind)}
            className={FIELD}
          >
            {RESOURCE_KINDS.map((k) => (
              <option key={k} value={k}>
                {KIND_LABELS[k]}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          Status
          <select
            value={form.status}
            onChange={(e) => set('status', e.target.value as ResourceStatus)}
            className={FIELD}
          >
            {RESOURCE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className={LABEL}>
          Provider
          <input
            value={form.provider}
            onChange={(e) => set('provider', e.target.value)}
            className={FIELD}
          />
        </label>
        <label className={LABEL}>
          Link
          <input
            type="url"
            value={form.url}
            onChange={(e) => set('url', e.target.value)}
            className={FIELD}
          />
        </label>
        <label className={LABEL}>
          Modules
          <input
            type="number"
            min={1}
            max={500}
            required
            value={form.module_count}
            onChange={(e) => set('module_count', Number(e.target.value))}
            className={FIELD}
          />
        </label>
        <label className={LABEL}>
          Duration (minutes)
          <input
            type="number"
            min={1}
            value={form.duration_minutes ?? ''}
            onChange={(e) =>
              set('duration_minutes', e.target.value ? Number(e.target.value) : null)
            }
            className={FIELD}
          />
        </label>
        <label className={`${LABEL} sm:col-span-2`}>
          Description
          <textarea
            rows={2}
            value={form.description}
            onChange={(e) => set('description', e.target.value)}
            className={FIELD}
          />
        </label>
      </div>

      <fieldset>
        <legend className={LABEL}>Skills taught</legend>
        <ul className="mt-1 space-y-1.5">
          {form.skills.map((link, index) => (
            <li key={link.skill} className="flex items-center gap-2">
              <select
                aria-label="Skill"
                value={link.skill}
                onChange={(e) => setLink(index, { skill: e.target.value })}
                className="flex-1 rounded-md border border-brand-100 bg-white px-2 py-1 text-sm text-ink"
              >
                {skills
                  .filter((s) => s.id === link.skill || !linked.has(s.id))
                  .map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
              </select>
              <select
                aria-label="Level"
                value={link.level}
                onChange={(e) => setLink(index, { level: Number(e.target.value) })}
                className="rounded-md border border-brand-100 bg-white px-2 py-1 text-sm text-ink"
              >
                {LEVELS.map((l) => (
                  <option key={l} value={l}>
                    L{l}
                  </option>
                ))}
              </select>
              <button
                type="button"
                onClick={() =>
                  set(
                    'skills',
                    form.skills.filter((_, i) => i !== index),
                  )
                }
                className="text-[12px] text-ink-soft hover:text-ink"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
        {unlinked.length > 0 && (
          <button
            type="button"
            onClick={() => set('skills', [...form.skills, { skill: unlinked[0].id, level: 1 }])}
            className="mt-2 text-[12px] font-semibold"
            style={{ color: 'var(--tenant-accent)' }}
          >
            + Add skill
          </button>
        )}
      </fieldset>

      {error && <p className="text-[12px] text-red-700">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg px-3.5 py-1.5 text-[13px] font-semibold text-white disabled:opacity-60"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {initial ? 'Save changes' : 'Create resource'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-lg border border-brand-100 px-3.5 py-1.5 text-[13px] font-semibold text-ink"
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
