/**
 * The roadmap spine: an ordered route of milestones from where the learner is
 * to their target grade. Cleared steps are checked, the current step is raised
 * into a card with its next resource, upcoming steps are quiet.
 */
import type { ReactNode } from 'react'

import { LEVEL_NAMES, type RoadmapStep } from '../types'
import { LevelMeter } from './LevelMeter'

interface RoadmapSpineProps {
  steps: RoadmapStep[]
  /** Extra content for an unmet step (e.g. its learning resources). */
  renderStepExtra?: (step: RoadmapStep) => ReactNode
}

export function RoadmapSpine({ steps, renderStepExtra }: RoadmapSpineProps) {
  const firstUpcomingId = steps.find((s) => s.status === 'upcoming')?.id
  return (
    <ol className="relative mt-5 space-y-4 pl-8">
      {/* the connecting line */}
      <span
        className="absolute bottom-2 left-[11px] top-2 w-0.5"
        style={{
          background:
            'linear-gradient(var(--tenant-accent) 55%, color-mix(in srgb, var(--tenant-accent) 22%, white) 55%)',
        }}
        aria-hidden="true"
      />

      {steps.map((step) => {
        if (step.status === 'current') {
          return (
            <li key={step.id} className="relative">
              <span
                className="absolute -left-[30px] top-0 h-5 w-5 rounded-full border-[3px] bg-white"
                style={{
                  borderColor: 'var(--tenant-accent)',
                  boxShadow: '0 0 0 4px color-mix(in srgb, var(--tenant-accent) 18%, white)',
                }}
                aria-hidden="true"
              />
              <div className="rounded-xl border border-brand-100 bg-white p-3.5 shadow-sm">
                <div className="flex items-baseline justify-between gap-2">
                  <span className="font-semibold text-ink">
                    Now · {step.skill} → {LEVEL_NAMES[step.targetLevel]}
                  </span>
                  {step.levelsToGo != null && (
                    <span
                      className="font-mono text-[10px]"
                      style={{ color: 'var(--tenant-accent)' }}
                    >
                      {step.levelsToGo} level to go
                    </span>
                  )}
                </div>
                <div className="mt-2">
                  <LevelMeter
                    currentLevel={step.currentLevel}
                    targetLevel={step.targetLevel}
                    label={step.skill}
                  />
                </div>
                {renderStepExtra ? (
                  renderStepExtra(step)
                ) : (
                  <button
                    className="mt-3 rounded-lg px-3.5 py-1.5 text-[13px] font-semibold text-white"
                    style={{ backgroundColor: 'var(--tenant-accent)' }}
                  >
                    Work on {step.skill}
                  </button>
                )}
              </div>
            </li>
          )
        }

        const cleared = step.status === 'cleared'
        return (
          <li key={step.id} className="relative">
            <span
              className="absolute -left-[28px] top-0.5 grid h-4 w-4 place-items-center rounded-full text-[9px] text-white"
              style={
                cleared
                  ? { backgroundColor: 'var(--tenant-accent)' }
                  : { backgroundColor: '#fff', border: '2px solid color-mix(in srgb, var(--tenant-accent) 35%, white)' }
              }
              aria-hidden="true"
            >
              {cleared ? '✓' : ''}
            </span>
            <div className="font-medium text-ink">
              {cleared ? '' : step.id === firstUpcomingId ? 'Next · ' : 'Then · '}
              {step.skill} → {LEVEL_NAMES[step.targetLevel]}
            </div>
            {step.note && <div className="text-[11.5px] text-ink-soft">{step.note}</div>}
            {!cleared && renderStepExtra?.(step)}
          </li>
        )
      })}
    </ol>
  )
}
