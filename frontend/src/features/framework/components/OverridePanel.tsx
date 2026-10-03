/**
 * Organization-specific customization of a global skill (copy-on-write): rename
 * it, relabel its status, or hide it for this tenant only. The shared global row
 * is never changed.
 */
import { useState } from 'react'

import { ConfirmAction } from '../../../components/ConfirmAction'
import { apiErrorMessage } from '../../../lib/apiError'
import type { ApiSkill } from '../../skills/types'
import { useOverrideSkill, useSkillOverrides } from '../api'

export function OverridePanel({ skill, onHidden }: { skill: ApiSkill; onHidden: () => void }) {
  const overrides = useSkillOverrides()
  const save = useOverrideSkill()
  const current = overrides.data?.find((o) => o.skill === skill.id)
  const [name, setName] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  if (overrides.isLoading) return <p className="text-ink-soft">Loading customization…</p>

  const shownName = name ?? current?.name ?? ''
  const originalName = current?.skill_name ?? skill.name

  return (
    <div className="space-y-4 rounded-xl border border-brand-100 bg-white p-4">
      <p className="text-[13px] text-ink-soft">
        <span className="font-semibold text-ink">{originalName}</span> is a global skill shared by
        every organization. Changes here apply to your organization only.
      </p>

      <label className="block text-[12px] font-semibold text-ink-soft">
        Display name for your organization
        <div className="mt-1 flex gap-2">
          <input
            value={shownName}
            placeholder={originalName}
            onChange={(e) => {
              setSaved(false)
              setName(e.target.value)
            }}
            className="w-full max-w-sm rounded-md border border-brand-100 bg-white px-2.5 py-1.5 text-[13px] text-ink"
          />
          <button
            type="button"
            disabled={save.isPending || name === null}
            onClick={() =>
              save.mutate(
                { skillId: skill.id, name: shownName.trim() },
                {
                  onSuccess: () => {
                    setName(null)
                    setSaved(true)
                  },
                },
              )
            }
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            Save name
          </button>
        </div>
        <span className="mt-1 block font-normal">Leave blank to use the global name.</span>
      </label>

      <div className="flex items-center gap-3 border-t border-brand-50 pt-3">
        <ConfirmAction
          label="Hide for my organization"
          prompt="Hide this skill from everyone in your organization?"
          confirmLabel="Hide"
          tone="danger"
          busy={save.isPending}
          onConfirm={() =>
            save.mutate({ skillId: skill.id, hidden: true }, { onSuccess: onHidden })
          }
        />
        <span className="text-[12px] text-ink-soft">
          Hidden skills move to “Hidden for your organization” on the framework page.
        </span>
      </div>

      {saved && <p className="text-[12.5px] text-brand-700">Saved ✓</p>}
      {save.isError && (
        <p role="alert" className="text-[12.5px] text-red-600">
          {apiErrorMessage(save.error, 'Could not save the customization.')}
        </p>
      )}
    </div>
  )
}
