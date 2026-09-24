/**
 * Placeholder for pages whose data/behaviour lands in Phase 1/2.
 *
 * Every empty state should eventually carry its next action (spec) — the
 * `action` slot is where that call-to-action goes when the feature is built.
 */
import type { ReactNode } from 'react'

interface PagePlaceholderProps {
  title: string
  description: string
  specRef?: string
  action?: ReactNode
}

export function PagePlaceholder({ title, description, specRef, action }: PagePlaceholderProps) {
  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-semibold text-slate-900">{title}</h1>
      <p className="mt-2 text-slate-600">{description}</p>
      {specRef && (
        <p className="mt-4 inline-block rounded bg-slate-100 px-2 py-1 font-mono text-xs text-slate-500">
          {specRef}
        </p>
      )}
      {action && <div className="mt-6">{action}</div>}
    </section>
  )
}
