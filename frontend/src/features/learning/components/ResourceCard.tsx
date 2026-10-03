/**
 * One learning resource with the learner's progress on it: title, "Course · 4 h ·
 * 2 of 6 modules", a progress bar, and the single next action (Start, Continue
 * module N / Mark module N done, or Completed).
 */
import type { ReactNode } from 'react'

import { resourceMeta } from '../format'
import type { LearningProgress, ResourceSummary } from '../types'

interface ResourceCardProps {
  resource: ResourceSummary
  progress?: LearningProgress | null
  /** Whether the viewer can record progress (skill.claim.submit). */
  canLearn: boolean
  busy?: boolean
  onStart: () => void
  onModuleDone: (progress: LearningProgress) => void
  /** Extra content under the meta line (e.g. skill chips in the library). */
  children?: ReactNode
}

const PRIMARY =
  'rounded-lg px-3 py-1 text-[12px] font-semibold text-white disabled:cursor-not-allowed disabled:opacity-60'
const SECONDARY =
  'rounded-lg border border-brand-100 bg-white px-3 py-1 text-[12px] font-semibold text-ink disabled:cursor-not-allowed disabled:opacity-60'

export function ResourceCard({
  resource,
  progress,
  canLearn,
  busy = false,
  onStart,
  onModuleDone,
  children,
}: ResourceCardProps) {
  const total = resource.module_count
  const done = progress?.completed_modules ?? 0
  const pct = Math.round((done / Math.max(1, total)) * 100)
  const status = progress?.status ?? 'not_started'
  const nextModule = Math.min(done + 1, total)

  return (
    <div className="rounded-lg border border-brand-100 bg-brand-50 px-3 py-2.5">
      <div className="flex items-center gap-3">
        <span
          className="grid h-8 w-8 flex-none place-items-center rounded-lg text-sm text-white"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
          aria-hidden="true"
        >
          {status === 'completed' ? '✓' : '▶'}
        </span>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-semibold text-ink">{resource.title}</div>
          <div className="text-[11px] text-ink-soft">{resourceMeta(resource, progress)}</div>
        </div>
        <div
          className="w-14 flex-none"
          role="progressbar"
          aria-label={`${resource.title} progress`}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
        >
          <div className="h-1.5 overflow-hidden rounded-full bg-brand-100">
            <div
              className="h-full rounded-full"
              style={{ width: `${pct}%`, backgroundColor: 'var(--tenant-accent)' }}
            />
          </div>
        </div>
      </div>

      {children}

      <div className="mt-2 flex flex-wrap items-center gap-2 pl-11">
        {canLearn && status === 'not_started' && (
          <button
            type="button"
            className={PRIMARY}
            style={{ backgroundColor: 'var(--tenant-accent)' }}
            disabled={busy}
            onClick={onStart}
          >
            Start
          </button>
        )}
        {canLearn && status === 'in_progress' && progress && (
          <>
            {resource.url && (
              <a
                href={resource.url}
                target="_blank"
                rel="noreferrer"
                className={PRIMARY}
                style={{ backgroundColor: 'var(--tenant-accent)' }}
              >
                Continue module {nextModule}
              </a>
            )}
            <button
              type="button"
              className={SECONDARY}
              disabled={busy}
              onClick={() => onModuleDone(progress)}
            >
              Mark module {nextModule} done
            </button>
          </>
        )}
        {status === 'completed' && (
          <span className="font-mono text-[10.5px] uppercase tracking-wide text-ink-soft">
            Completed
          </span>
        )}
        {resource.url && status !== 'in_progress' && (
          <a
            href={resource.url}
            target="_blank"
            rel="noreferrer"
            className="text-[12px] font-semibold"
            style={{ color: 'var(--tenant-accent)' }}
          >
            Open ↗
          </a>
        )}
      </div>
    </div>
  )
}
