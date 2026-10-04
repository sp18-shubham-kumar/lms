/**
 * A two-step button for state-changing actions: the first click asks, the second
 * commits. Keeps the "explicit confirm, not optimistic" rule without a modal.
 */
import { useState, type ReactNode } from 'react'

interface ConfirmActionProps {
  label: string
  /** The question shown in place of the button once armed. */
  prompt: ReactNode
  confirmLabel?: string
  onConfirm: () => void
  busy?: boolean
  tone?: 'accent' | 'danger' | 'secondary'
}

const SECONDARY =
  'rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50'

export function ConfirmAction({
  label,
  prompt,
  confirmLabel = 'Confirm',
  onConfirm,
  busy,
  tone = 'secondary',
}: ConfirmActionProps) {
  const [armed, setArmed] = useState(false)

  if (!armed) {
    return (
      <button
        type="button"
        onClick={() => setArmed(true)}
        disabled={busy}
        className={
          tone === 'secondary'
            ? SECONDARY
            : tone === 'danger'
              ? 'rounded-lg border border-red-200 px-3 py-1.5 text-[13px] font-semibold text-red-700 hover:bg-red-50 disabled:opacity-50'
              : 'rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50'
        }
        style={tone === 'accent' ? { backgroundColor: 'var(--tenant-accent)' } : undefined}
      >
        {label}
      </button>
    )
  }

  return (
    <span
      role="group"
      aria-label={`Confirm ${label}`}
      className="inline-flex items-center gap-2 rounded-lg border border-brand-100 bg-brand-50 px-2.5 py-1 text-[12.5px] text-ink"
    >
      <span>{prompt}</span>
      <button
        type="button"
        onClick={() => {
          setArmed(false)
          onConfirm()
        }}
        disabled={busy}
        className={`rounded-md px-2 py-0.5 font-semibold text-white disabled:opacity-50 ${
          tone === 'danger' ? 'bg-red-600' : ''
        }`}
        style={tone === 'danger' ? undefined : { backgroundColor: 'var(--tenant-accent)' }}
      >
        {confirmLabel}
      </button>
      <button
        type="button"
        onClick={() => setArmed(false)}
        className="rounded-md px-2 py-0.5 font-semibold text-ink-soft hover:bg-white"
      >
        Cancel
      </button>
    </span>
  )
}
