/** Admin API hooks: roles (read) + member import (dry-run / commit). */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { ImportDiff, Role } from './types'

export function useRoles() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['roles', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<Role>>('/authz/roles/', { params: { page_size: 200 } })
      return resp.data.results
    },
  })
}

export function useImportMembers() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ csv, commit }: { csv: string; commit: boolean }) => {
      const resp = await api.post<ImportDiff>(
        '/identity/members/import/',
        { csv },
        { params: commit ? { commit: 'true' } : {} },
      )
      return resp.data
    },
    onSuccess: (_data, variables) => {
      // A committed import changes the directory; refresh it.
      if (variables.commit) qc.invalidateQueries({ queryKey: ['people', tenant?.id] })
    },
  })
}
