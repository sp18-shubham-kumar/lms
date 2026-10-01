/**
 * One skill in the catalogue, wired to the self-declaration API. If the learner
 * has declared the skill it shows their level with a Remove action; otherwise a
 * small level picker + Declare.
 */
import { useState } from 'react'

import { LevelMeter } from '../../roadmap/components/LevelMeter'
import type { LevelValue } from '../../roadmap/types'
import { LEVEL_LABELS, type ApiSkill, type SelfDeclaration } from '../types'

interface SkillCardProps {
  skill: ApiSkill
  domainName: string
  declaration?: SelfDeclaration
  busy?: boolean
  canDeclare: boolean
  onDeclare: (level: number) => void
  onRemove: (declarationId: string) => void
}

export function SkillCard({
  skill,
  domainName,
  declaration,
  busy,
  canDeclare,
  onDeclare,
  onRemove,
}: SkillCardProps) {
  const [level, setLevel] = useState(2)
  const declared = Boolean(declaration)

  return (
    <div className="flex flex-col rounded-xl border border-brand-100 bg-white p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-ink">{skill.name}</div>
          <div className="text-[11.5px] text-ink-soft">{domainName}</div>
        </div>
        {declared && (
          <span className="font-mono text-[10px] text-ink-soft">
            {LEVEL_LABELS[declaration!.level] ?? `L${declaration!.level}`}
          </span>
        )}
      </div>

      {declared && (
        <div className="mt-2.5">
          <LevelMeter currentLevel={Math.min(4, declaration!.level) as LevelValue} label={skill.name} />
        </div>
      )}

      <div className="mt-3">
        {declared ? (
          <button
            onClick={() => onRemove(declaration!.id)}
            disabled={busy}
            className="inline-flex items-center rounded-lg border border-brand-200 px-2.5 py-1 text-[11.5px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
          >
            Declared ✓ · Remove
          </button>
        ) : canDeclare ? (
          <div className="flex items-center gap-2">
            <select
              value={level}
              onChange={(e) => setLevel(Number(e.target.value))}
              className="rounded-md border border-brand-100 bg-white px-2 py-1 text-[11.5px] text-ink"
              aria-label={`Level for ${skill.name}`}
            >
              <option value={1}>Aware</option>
              <option value={2}>Working</option>
              <option value={3}>Proficient</option>
              <option value={4}>Expert</option>
            </select>
            <button
              onClick={() => onDeclare(level)}
              disabled={busy}
              className="inline-flex items-center rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-white disabled:opacity-50"
              style={{ backgroundColor: 'var(--tenant-accent)' }}
            >
              + Declare
            </button>
          </div>
        ) : (
          <span className="text-[11px] text-ink-soft">View only</span>
        )}
      </div>
    </div>
  )
}
