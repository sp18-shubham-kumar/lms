/**
 * The skill requirements of one job profile version (P2-R5).
 *
 * Read-only unless the version is a draft — published versions are frozen so
 * readiness computed against them stays meaningful.
 */
import { useState, type FormEvent } from 'react'

import { apiErrorMessage } from '../../../lib/errors'
import { useSkills } from '../../skills/api'
import { useAddRequirement, useRemoveRequirement, useRequirements, useSkillLevels } from '../api'
import { levelLabel } from '../levels'
import { CRITICALITIES, CRITICALITY_HELP, REQUIREMENT_LEVELS, type Criticality } from '../types'
import { CARD, INPUT, LABEL, PRIMARY_BUTTON, PRIMARY_STYLE, SECONDARY_BUTTON } from './styles'

export function RequirementsEditor({
  profileId,
  editable,
}: {
  profileId: string
  editable: boolean
}) {
  const requirements = useRequirements(profileId)
  const skills = useSkills()
  const remove = useRemoveRequirement(profileId)

  // Prefer the tenant-resolved name from the skills list (it applies renames).
  const skillName = (id: string, fallback: string) =>
    skills.data?.find((s) => s.id === id)?.name ?? fallback

  const rows = requirements.data ?? []

  return (
    <div className={`mt-5 ${CARD}`}>
      <h2 className="text-sm font-semibold text-ink">Skill requirements</h2>
      {!editable && (
        <p className="mt-1 text-[12.5px] text-ink-soft">
          This version is locked. Edit it as a new version to change requirements.
        </p>
      )}

      {requirements.isLoading && <p className="mt-3 text-ink-soft">Loading requirements…</p>}
      {requirements.isError && <p className="mt-3 text-ink-soft">Could not load requirements.</p>}
      {requirements.data && rows.length === 0 && (
        <p className="mt-3 text-sm text-ink-soft">No requirements yet.</p>
      )}

      {rows.length > 0 && (
        <table className="mt-3 w-full text-left text-sm">
          <thead>
            <tr className={LABEL}>
              <th className="py-1 font-normal">Skill</th>
              <th className="py-1 font-normal">Minimum level</th>
              <th className="py-1 font-normal">Criticality</th>
              {editable && <th className="py-1 font-normal" aria-label="Actions" />}
            </tr>
          </thead>
          <tbody className="divide-y divide-brand-100">
            {rows.map((r) => (
              <tr key={r.id}>
                <td className="py-2 font-medium text-ink">{skillName(r.skill, r.skill_name)}</td>
                <td className="py-2 text-ink">{levelLabel(r.min_level)}</td>
                <td className="py-2 text-ink" title={CRITICALITY_HELP[r.criticality]}>
                  {r.criticality}
                </td>
                {editable && (
                  <td className="py-2 text-right">
                    <button
                      type="button"
                      className={SECONDARY_BUTTON}
                      disabled={remove.isPending}
                      onClick={() => remove.mutate(r.id)}
                      aria-label={`Remove ${skillName(r.skill, r.skill_name)}`}
                    >
                      Remove
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {remove.isError && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {apiErrorMessage(remove.error, 'Could not remove the requirement.')}
        </p>
      )}

      {editable && (
        <AddRequirementRow
          profileId={profileId}
          taken={new Set(rows.map((r) => r.skill))}
          options={(skills.data ?? []).filter((s) => s.status !== 'retired')}
        />
      )}
    </div>
  )
}

function AddRequirementRow({
  profileId,
  taken,
  options,
}: {
  profileId: string
  taken: Set<string>
  options: Array<{ id: string; name: string }>
}) {
  const [skill, setSkill] = useState('')
  const [level, setLevel] = useState(2)
  const [criticality, setCriticality] = useState<Criticality>('core')
  const rubric = useSkillLevels(skill || null)
  const add = useAddRequirement(profileId)

  const available = options.filter((s) => !taken.has(s.id))

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!skill) return
    add.mutate({ skill, min_level: level, criticality }, { onSuccess: () => setSkill('') })
  }

  return (
    <form
      onSubmit={submit}
      className="mt-4 flex flex-wrap items-center gap-2 border-t border-brand-100 pt-3"
    >
      <select
        value={skill}
        onChange={(e) => setSkill(e.target.value)}
        aria-label="Skill"
        className={INPUT}
      >
        <option value="">Add a skill…</option>
        {available.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      <select
        value={level}
        onChange={(e) => setLevel(Number(e.target.value))}
        aria-label="Minimum level"
        className={INPUT}
      >
        {REQUIREMENT_LEVELS.map((n) => (
          <option key={n} value={n}>
            {levelLabel(n, rubric.data)}
          </option>
        ))}
      </select>
      <select
        value={criticality}
        onChange={(e) => setCriticality(e.target.value as Criticality)}
        aria-label="Criticality"
        className={INPUT}
      >
        {CRITICALITIES.map((c) => (
          <option key={c} value={c} title={CRITICALITY_HELP[c]}>
            {c}
          </option>
        ))}
      </select>
      <button
        type="submit"
        disabled={!skill || add.isPending}
        className={PRIMARY_BUTTON}
        style={PRIMARY_STYLE}
      >
        Add requirement
      </button>
      {add.isError && (
        <p role="alert" className="w-full text-sm text-red-600">
          {apiErrorMessage(add.error, 'Could not add the requirement.')}
        </p>
      )}
    </form>
  )
}
