/**
 * A four-tick skill-level meter (Aware → Working → Proficient → Expert).
 *
 * Filled ticks show the current level; the target level is ringed so a learner
 * can see "where I am" vs "where I need to be" at a glance. Colour derives from
 * the tenant accent so branding applies without a rebuild.
 */
import type { LevelValue } from '../types'

interface LevelMeterProps {
  currentLevel: LevelValue
  targetLevel?: LevelValue
  /** Accessible label context, e.g. the skill name. */
  label?: string
}

const TICKS: LevelValue[] = [1, 2, 3, 4]

export function LevelMeter({ currentLevel, targetLevel, label }: LevelMeterProps) {
  return (
    <div
      className="inline-flex items-center gap-1"
      role="img"
      aria-label={
        label
          ? `${label}: level ${currentLevel} of 4${targetLevel ? `, target ${targetLevel}` : ''}`
          : undefined
      }
    >
      {TICKS.map((tick) => {
        const filled = tick <= currentLevel
        const isTarget = tick === targetLevel
        return (
          <span
            key={tick}
            className="h-1.5 w-4 rounded-full"
            style={{
              backgroundColor: 'var(--tenant-accent)',
              opacity: filled ? 1 : 0.16,
              boxShadow: isTarget ? '0 0 0 1.5px color-mix(in srgb, var(--tenant-accent) 55%, white)' : undefined,
            }}
          />
        )
      })}
    </div>
  )
}
