/** A read-only value with a Copy button, for invite links shown once. */
import { useState } from 'react'

export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
    } catch {
      // Clipboard denied or not a secure context; the field is still selectable.
    }
  }

  return (
    <label className="block text-[12.5px]">
      <span className="font-semibold text-ink">{label}</span>
      <div className="mt-1 flex gap-2">
        <input
          readOnly
          value={value}
          onFocus={(e) => e.currentTarget.select()}
          className="w-full rounded-lg border border-brand-100 bg-ground px-3 py-1.5 font-mono text-[12px] text-ink"
        />
        <button
          type="button"
          onClick={() => void copy()}
          className="shrink-0 rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50"
        >
          {copied ? 'Copied ✓' : 'Copy'}
        </button>
      </div>
    </label>
  )
}
