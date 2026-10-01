/**
 * Readiness / job-profile API hooks (TanStack Query over lib/api.ts).
 *
 * GET /profiles/job-profiles/ is readable with `directory.view` (reads were
 * opened up so learners can browse the career ladder); writes still require
 * `jobprofile.edit`.
 */
import { useQuery } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { JobProfile, Readiness } from './types'

export function useJobProfiles(enabled: boolean) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['job-profiles', tenant?.id],
    enabled: enabled && Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<JobProfile>>('/profiles/job-profiles/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useReadiness(target: string | null) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['readiness', tenant?.id, target],
    enabled: Boolean(tenant?.id && target),
    queryFn: async () => {
      const resp = await api.get<Readiness>('/profiles/me/readiness/', {
        params: { target },
      })
      return resp.data
    },
  })
}
