import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { DirectoryPerson, Paginated, PeopleFilters } from './types'

/** Drop empty filters, and `level` when no skill is chosen (the API ignores it then). */
export function toPeopleParams(filters: PeopleFilters): Record<string, string | number> {
  const params: Record<string, string | number> = {}
  if (filters.q?.trim()) params.q = filters.q.trim()
  if (filters.skill) {
    params.skill = filters.skill
    if (filters.level) params.level = filters.level
  }
  if (filters.org_unit) params.org_unit = filters.org_unit
  return params
}

export function usePeople(page: number, filters: PeopleFilters = {}, pageSize?: number) {
  const { tenant } = useTenant()
  const params = toPeopleParams(filters)
  return useQuery({
    queryKey: ['people', tenant?.id, page, params, pageSize ?? null],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<DirectoryPerson>>('/identity/people/', {
        params: { page, ...params, ...(pageSize ? { page_size: pageSize } : {}) },
      })
      return resp.data
    },
  })
}
