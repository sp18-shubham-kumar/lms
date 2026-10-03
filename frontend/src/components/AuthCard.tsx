/** Centered card used by the signed-out screens: sign in, accept invite, choose org. */
import type { ReactNode } from 'react'

export function AuthCard({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle?: ReactNode
  children: ReactNode
}) {
  return (
    <div className="flex h-full items-center justify-center bg-ground p-6">
      <div className="w-full max-w-sm space-y-4 rounded-xl border border-brand-100 bg-white p-8 shadow-sm">
        <div>
          <div className="mb-3 flex items-center gap-2">
            <span
              className="inline-block h-5 w-5 rounded"
              style={{ backgroundColor: 'var(--tenant-accent)' }}
            />
            <span className="text-[13px] font-semibold text-ink">Skills LMS</span>
          </div>
          <h1 className="text-xl font-semibold text-ink">{title}</h1>
          {subtitle && <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>}
        </div>
        {children}
      </div>
    </div>
  )
}

export const authInputClass =
  'mt-1 w-full rounded-lg border border-brand-100 px-3 py-2 text-ink outline-none focus:border-brand-300'

export const authPrimaryButtonClass =
  'w-full rounded-lg py-2 font-semibold text-white disabled:opacity-60'
