/** Lifecycle + ownership chips for a skill row. */
import type { ApiSkill } from '../../skills/types'

const STATUS_STYLE: Record<string, string> = {
  draft: 'border-amber-200 bg-amber-50 text-amber-800',
  published: 'border-brand-200 bg-brand-50 text-brand-700',
  retired: 'border-gray-200 bg-gray-50 text-gray-500',
}

export function StatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide ${
        STATUS_STYLE[status] ?? STATUS_STYLE.retired
      }`}
    >
      {status}
    </span>
  )
}

export function SkillChips({ skill }: { skill: ApiSkill }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <StatusBadge status={skill.status} />
      <span className="font-mono text-[10.5px] text-ink-soft">v{skill.version}</span>
      {skill.tenant === null && (
        <span className="rounded-full border border-brand-100 px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide text-ink-soft">
          global
        </span>
      )}
    </span>
  )
}
