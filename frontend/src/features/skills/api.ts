/**
 * Skills API hooks (TanStack Query over lib/api.ts).
 *
 * Query keys are tenant-scoped so one tenant's data never leaks into another's
 * view. Mutations invalidate the affected queries so the UI refreshes without a
 * page reload.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { ApiSkill, SelfDeclaration, SkillDomain } from './types'

export function useSkillDomains() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['skill-domains', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<SkillDomain>>('/skills/domains/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useSkills(enabled = true) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['skills', tenant?.id],
    enabled: enabled && Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<ApiSkill>>('/skills/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useMyDeclarations() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['my-declarations', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<SelfDeclaration>>('/skills/me/declarations/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useDeclareSkill() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: { skill: string; level: number; note?: string }) => {
      const resp = await api.post<SelfDeclaration>('/skills/me/declarations/', input)
      return resp.data
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-declarations', tenant?.id] })
    },
  })
}

export function useRemoveDeclaration() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (declarationId: string) => {
      await api.delete(`/skills/me/declarations/${declarationId}/`)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['my-declarations', tenant?.id] })
    },
  })
}
