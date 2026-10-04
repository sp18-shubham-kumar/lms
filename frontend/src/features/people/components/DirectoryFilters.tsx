/**
 * Directory filter bar: free-text search, skill (+ minimum level) and org unit.
 * Level only applies with a skill, so it is disabled until one is picked.
 */
import { LEVEL_LABELS } from '../../skills/types'
import type { ApiSkill } from '../../skills/types'
import type { OrgUnit } from '../../team/types'
import type { PeopleFilters } from '../types'

interface DirectoryFiltersProps {
  value: PeopleFilters
  onChange: (next: PeopleFilters) => void
  skills: ApiSkill[]
  orgUnits: OrgUnit[]
}

const FIELD =
  'rounded-lg border border-brand-100 bg-white px-3 py-1.5 text-[13px] text-ink disabled:opacity-50'

export function DirectoryFilters({ value, onChange, skills, orgUnits }: DirectoryFiltersProps) {
  const hasFilters = Boolean(value.q || value.skill || value.org_unit)
  return (
    <div className="flex flex-wrap items-center gap-2">
      <input
        type="search"
        aria-label="Search people"
        placeholder="Search name or email"
        value={value.q ?? ''}
        onChange={(e) => onChange({ ...value, q: e.target.value })}
        className={`${FIELD} w-56`}
      />
      <select
        aria-label="Skill"
        value={value.skill ?? ''}
        onChange={(e) =>
          onChange({ ...value, skill: e.target.value || undefined, level: undefined })
        }
        className={FIELD}
      >
        <option value="">Any skill</option>
        {skills.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}
          </option>
        ))}
      </select>
      <select
        aria-label="Minimum level"
        value={value.level ?? ''}
        disabled={!value.skill}
        onChange={(e) =>
          onChange({ ...value, level: e.target.value ? Number(e.target.value) : undefined })
        }
        className={FIELD}
      >
        <option value="">Any level</option>
        {[1, 2, 3, 4].map((level) => (
          <option key={level} value={level}>
            {LEVEL_LABELS[level]}+
          </option>
        ))}
      </select>
      <select
        aria-label="Org unit"
        value={value.org_unit ?? ''}
        onChange={(e) => onChange({ ...value, org_unit: e.target.value || undefined })}
        className={FIELD}
      >
        <option value="">All org units</option>
        {orgUnits.map((u) => (
          <option key={u.id} value={u.id}>
            {'\u00a0\u00a0'.repeat(Math.max(0, u.path.split('.').length - 1))}
            {u.name}
          </option>
        ))}
      </select>
      {hasFilters && (
        <button
          onClick={() => onChange({})}
          className="rounded-lg px-2 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50"
        >
          Clear
        </button>
      )}
    </div>
  )
}
