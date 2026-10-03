/**
 * Renders its children only for callers holding `capability`. The nav already
 * hides the link; this covers a typed or bookmarked URL. The API enforces the
 * same capability, so this is a courtesy, not the security boundary.
 */
import type { ReactNode } from 'react'

import { useAuth } from '../lib/auth'

export function CapabilityGate({
  capability,
  children,
}: {
  capability: string
  children: ReactNode
}) {
  const { hasCapability } = useAuth()
  if (!hasCapability(capability)) {
    return <p className="text-ink-soft">You don’t have access to this page.</p>
  }
  return <>{children}</>
}
