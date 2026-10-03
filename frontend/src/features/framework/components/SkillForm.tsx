/**
 * Skill definition form, shared by "New skill" and the editor's Definition tab.
 * The slug follows the name until the author edits it by hand.
 */
import { useState, type FormEvent } from 'react'

import { apiErrorMessage } from '../../../lib/apiError'
import type { SkillDomain } from '../../skills/types'
import { slugify, type SkillInput } from '../types'

interface SkillFormProps {
  domains: SkillDomain[]
  initial?: SkillInput
  submitLabel: string
  busy?: boolean
  error?: unknown
  /** When set, the slug is fixed (it identifies the skill across versions). */
  lockSlug?: boolean
  onSubmit: (input: SkillInput) => void
  onCancel?: () => void
}

const INPUT =
  'w-full rounded-md border border-brand-100 bg-white px-2.5 py-1.5 text-[13px] text-ink'

export function SkillForm({
  domains,
  initial,
  submitLabel,
  busy,
  error,
  lockSlug,
  onSubmit,
  onCancel,
}: SkillFormProps) {
  const [form, setForm] = useState<SkillInput>(
    initial ?? { domain: domains[0]?.id ?? '', name: '', slug: '', description: '' },
  )
  const [slugTouched, setSlugTouched] = useState(Boolean(initial))

  const set = (patch: Partial<SkillInput>) => setForm((prev) => ({ ...prev, ...patch }))

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault()
    onSubmit({ ...form, name: form.name.trim(), slug: form.slug.trim() })
  }

  return (
    <form onSubmit={handleSubmit} className="grid gap-3 sm:grid-cols-2">
      <label className="text-[12px] font-semibold text-ink-soft">
        Name
        <input
          required
          value={form.name}
          onChange={(e) =>
            set({ name: e.target.value, ...(slugTouched ? {} : { slug: slugify(e.target.value) }) })
          }
          className={`mt-1 ${INPUT}`}
        />
      </label>
      <label className="text-[12px] font-semibold text-ink-soft">
        Slug
        <input
          required
          value={form.slug}
          readOnly={lockSlug}
          onChange={(e) => {
            setSlugTouched(true)
            set({ slug: slugify(e.target.value) })
          }}
          className={`mt-1 font-mono ${INPUT} ${lockSlug ? 'bg-brand-50/50 text-ink-soft' : ''}`}
        />
      </label>
      <label className="text-[12px] font-semibold text-ink-soft">
        Domain
        <select
          required
          value={form.domain}
          onChange={(e) => set({ domain: e.target.value })}
          className={`mt-1 ${INPUT}`}
        >
          <option value="" disabled>
            Choose a domain…
          </option>
          {domains.map((d) => (
            <option key={d.id} value={d.id}>
              {d.name}
            </option>
          ))}
        </select>
      </label>
      <label className="text-[12px] font-semibold text-ink-soft">
        External code <span className="font-normal">(optional)</span>
        <input
          value={form.external_code ?? ''}
          onChange={(e) => set({ external_code: e.target.value })}
          className={`mt-1 font-mono ${INPUT}`}
        />
      </label>
      <label className="text-[12px] font-semibold text-ink-soft sm:col-span-2">
        Description
        <textarea
          rows={3}
          value={form.description ?? ''}
          onChange={(e) => set({ description: e.target.value })}
          className={`mt-1 ${INPUT}`}
        />
      </label>
      <div className="flex items-center gap-2 sm:col-span-2">
        <button
          type="submit"
          disabled={busy}
          className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50"
          >
            Cancel
          </button>
        )}
        {error != null && (
          <span role="alert" className="text-[12.5px] text-red-600">
            {apiErrorMessage(error, 'Could not save the skill.')}
          </span>
        )}
      </div>
    </form>
  )
}
