/** Team readiness API hooks (capability: report.org.view). */
import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { Heatmap, OrgUnit, ReadinessSnapshot } from './types'

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

export function useOrgUnits() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['org-units', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<OrgUnit>>('/identity/org-units/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useHeatmap(orgUnit: string | null, jobProfile: string | null) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['heatmap', tenant?.id, orgUnit, jobProfile],
    enabled: Boolean(tenant?.id && orgUnit && jobProfile),
    queryFn: async () => {
      const resp = await api.get<Heatmap>('/profiles/heatmap/', {
        params: { org_unit: orgUnit, job_profile: jobProfile },
      })
      return resp.data
    },
  })
}
