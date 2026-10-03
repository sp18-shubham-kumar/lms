/**
 * A destructive action that asks once inline before it runs ("Offboard" →
 * "Confirm offboard?"). Pessimistic by design: nothing happens on the first click.
 */
import { useState } from 'react'

import { DANGER_BUTTON, SECONDARY_BUTTON } from './styles'

interface ConfirmButtonProps {
  label: string
  confirmLabel: string
  onConfirm: () => void
  disabled?: boolean
}

export function ConfirmButton({ label, confirmLabel, onConfirm, disabled }: ConfirmButtonProps) {
  const [armed, setArmed] = useState(false)
  if (!armed) {
    return (
      <button className={SECONDARY_BUTTON} disabled={disabled} onClick={() => setArmed(true)}>
        {label}
      </button>
    )
  }
  return (
    <span className="inline-flex gap-1">
      <button
        className={DANGER_BUTTON}
        disabled={disabled}
        onClick={() => {
          setArmed(false)
          onConfirm()
        }}
      >
        {confirmLabel}
      </button>
      <button className={SECONDARY_BUTTON} onClick={() => setArmed(false)}>
        Cancel
      </button>
    </span>
  )
}
