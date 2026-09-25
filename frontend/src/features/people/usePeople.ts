import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { DirectoryPerson, Paginated } from './types'

export function usePeople(page: number) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['people', tenant?.id, page],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<DirectoryPerson>>('/identity/people/', {
        params: { page },
      })
      return resp.data
    },
  })
}
