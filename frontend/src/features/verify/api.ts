/**
 * Verifier queue hooks (`skill.verify`). Reviews are pessimistic: the row only
 * leaves the queue once the server has recorded the assertion or rejection.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'

export type ClaimStatus = 'pending' | 'verified' | 'rejected' | 'all'

export interface SkillClaim {
  id: string
  membership: string
  person_name: string
  person_email: string
  skill: string
  skill_name: string
  level: number
  note: string
  review_status: Exclude<ClaimStatus, 'all'>
  reviewed_at: string | null
  review_note: string
  created_at: string
}

const claimsKey = (tenantId?: string) => ['skill-claims', tenantId] as const

export function useClaims(status: ClaimStatus) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: [...claimsKey(tenant?.id), status],
    enabled: Boolean(tenant?.id),
    queryFn: async () =>
      (
        await api.get<Paginated<SkillClaim>>('/skills/claims/', {
          params: { status, page_size: 200 },
        })
      ).data.results,
  })
}

function useInvalidateClaims() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return () => qc.invalidateQueries({ queryKey: claimsKey(tenant?.id) })
}

export function useVerifyClaim() {
  const invalidate = useInvalidateClaims()
  return useMutation({
    mutationFn: async ({ id, level, note }: { id: string; level: number; note: string }) =>
      (await api.post(`/skills/claims/${id}/verify/`, { level, note })).data,
    onSuccess: invalidate,
  })
}

export function useRejectClaim() {
  const invalidate = useInvalidateClaims()
  return useMutation({
    mutationFn: async ({ id, note }: { id: string; note: string }) =>
      (await api.post<SkillClaim>(`/skills/claims/${id}/reject/`, { note })).data,
    onSuccess: invalidate,
  })
}
