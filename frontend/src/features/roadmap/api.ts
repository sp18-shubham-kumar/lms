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
import { latestVersions } from '../career-paths/lineage'
import type { Paginated } from '../people/types'
import type { JobProfile, Readiness } from './types'

/**
 * Targetable profiles: published only, newest version of each grade. Drafts are
 * work in progress and retired grades are gone, so neither is offered as a target.
 */
export function useJobProfiles(enabled: boolean) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['job-profiles', tenant?.id, 'targets'],
    enabled: enabled && Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<JobProfile>>('/profiles/job-profiles/', {
        params: { page_size: 200, status: 'published' },
      })
      return latestVersions(resp.data.results)
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
