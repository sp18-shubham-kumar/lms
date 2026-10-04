import type { ProfileStatus } from '../types'

const STYLES: Record<ProfileStatus, string> = {
  draft: 'border-amber-300 bg-amber-50 text-amber-800',
  published: 'border-emerald-300 bg-emerald-50 text-emerald-800',
  retired: 'border-brand-200 bg-brand-50 text-ink-soft',
}

/** Lifecycle badge for a job profile version; the word carries the meaning, not the color. */
export function ProfileStatusBadge({ status }: { status: string }) {
  const style = STYLES[status as ProfileStatus] ?? STYLES.retired
  return (
    <span
      className={`inline-block rounded-full border px-2 py-0.5 font-mono text-[10px] uppercase tracking-[0.1em] ${style}`}
    >
      {status}
    </span>
  )
}
