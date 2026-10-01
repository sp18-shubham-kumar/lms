/** Team readiness API hooks (capability: report.org.view). */
import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { ReadinessSnapshot } from './types'

export function useTeamReadiness(jobProfile?: string) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['team-readiness', tenant?.id, jobProfile ?? null],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<ReadinessSnapshot>>('/profiles/readiness/', {
        params: { page_size: 200, ...(jobProfile ? { job_profile: jobProfile } : {}) },
      })
      return resp.data.results
    },
  })
}
