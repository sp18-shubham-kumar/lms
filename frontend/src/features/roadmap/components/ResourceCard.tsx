/**
 * The "do this next" card that sits inside the current roadmap step — the whole
 * point of the Path direction: one obvious next action, not a wall of courses.
 */
import type { StepResource } from '../types'

interface ResourceCardProps {
  resource: StepResource
}

export function ResourceCard({ resource }: ResourceCardProps) {
  const progress = Math.round((resource.modulesDone / resource.modulesTotal) * 100)
  return (
    <div className="mt-3 flex items-center gap-3 rounded-lg border border-brand-100 bg-brand-50 px-3 py-2.5">
      <span
        className="grid h-8 w-8 flex-none place-items-center rounded-lg text-sm text-white"
        style={{ backgroundColor: 'var(--tenant-accent)' }}
        aria-hidden="true"
      >
        ▶
      </span>
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px] font-semibold text-ink">{resource.title}</div>
        <div className="text-[11px] text-ink-soft">
          {resource.kind} · {resource.duration} · {resource.modulesDone} of {resource.modulesTotal} modules
          done
        </div>
      </div>
      <div className="w-14 flex-none" aria-hidden="true">
        <div className="h-1.5 overflow-hidden rounded-full bg-brand-100">
          <div
            className="h-full rounded-full"
            style={{ width: `${progress}%`, backgroundColor: 'var(--tenant-accent)' }}
          />
        </div>
      </div>
    </div>
  )
}
