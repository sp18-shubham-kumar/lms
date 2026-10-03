/** Switch into one of the signed-in person's organizations and load its session. */
import { useCallback } from 'react'

import { useAuth, type Membership } from './auth'
import { useTenant } from './tenant'

export function useEnterTenant() {
  const { loadSession } = useAuth()
  const { setTenant } = useTenant()

  return useCallback(
    async (m: Membership) => {
      setTenant({ id: m.tenant_id, name: m.name, accentColor: m.accent_color || undefined })
      await loadSession()
    },
    [loadSession, setTenant],
  )
}
