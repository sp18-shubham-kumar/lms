import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { PersonProfile } from './types'

/** A member's profile. Pass `'me'` for the signed-in person's own profile. */
export function usePersonProfile(personId: string | undefined) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['person-profile', tenant?.id, personId],
    enabled: Boolean(tenant?.id && personId),
    queryFn: async () => {
      const resp = await api.get<PersonProfile>(`/identity/people/${personId}/`)
      return resp.data
    },
  })
}
