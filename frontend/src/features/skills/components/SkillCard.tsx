/**
 * One skill in the catalogue. Shows the learner's current level and either an
 * "on your path" marker or an "add to route" action. The toggle is local state
 * for the demo; later it becomes a mutation.
 */
import { useState } from 'react'

import { LevelMeter } from '../../roadmap/components/LevelMeter'
import { LEVEL_NAMES } from '../../roadmap/types'
import type { CatalogueSkill } from '../types'

interface SkillCardProps {
  skill: CatalogueSkill
}

export function SkillCard({ skill }: SkillCardProps) {
  const [onRoute, setOnRoute] = useState(skill.onRoute)

  return (
    <div className="flex flex-col rounded-xl border border-brand-100 bg-white p-3.5">
      <div className="flex items-start justify-between gap-2">
        <div>
          <div className="font-semibold text-ink">{skill.name}</div>
          <div className="text-[11.5px] text-ink-soft">
            {skill.domain} ·{' '}
            {skill.requiredForTarget ? 'on your route' : 'not required for L2'}
          </div>
        </div>
        {skill.myLevel > 0 && (
          <span className="font-mono text-[10px] text-ink-soft">{LEVEL_NAMES[skill.myLevel]}</span>
        )}
      </div>

      <div className="mt-2.5">
        <LevelMeter currentLevel={skill.myLevel} label={skill.name} />
      </div>

      <div className="mt-3">
        {onRoute ? (
          <span className="inline-flex items-center rounded-lg border border-brand-200 px-2.5 py-1 text-[11.5px] font-semibold text-brand-700">
            On your path ✓
          </span>
        ) : (
          <button
            onClick={() => setOnRoute(true)}
            className="inline-flex items-center rounded-lg px-2.5 py-1 text-[11.5px] font-semibold text-white"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            + Add to route
          </button>
        )}
      </div>
    </div>
  )
}
