/**
 * Skill framework authoring hooks (TanStack Query over lib/api.ts).
 *
 * Every query key carries the tenant id. Writes are pessimistic: the UI waits for
 * the server and then invalidates exactly the queries the write affected.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenantId } from '../../lib/useTenantId'
import type { Paginated } from '../people/types'
import type { ApiSkill, SkillDomain } from '../skills/types'
import type { EdgeKind, SkillEdge, SkillInput, SkillLevel, SkillOverride } from './types'

const keys = {
  skills: (tenantId?: string) => ['skills', tenantId] as const,
  domains: (tenantId?: string) => ['skill-domains', tenantId] as const,
  skill: (tenantId: string | undefined, id: string) => ['skill', tenantId, id] as const,
  levels: (tenantId: string | undefined, id: string) => ['skill-levels', tenantId, id] as const,
  edges: (tenantId: string | undefined, id: string) => ['skill-edges', tenantId, id] as const,
  versions: (tenantId: string | undefined, id: string) => ['skill-versions', tenantId, id] as const,
  overrides: (tenantId?: string) => ['skill-overrides', tenantId] as const,
}

export function useSkill(id: string) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: keys.skill(tenantId, id),
    enabled: Boolean(tenantId && id),
    queryFn: async () => (await api.get<ApiSkill>(`/skills/${id}/`)).data,
  })
}

export function useSkillLevels(id: string) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: keys.levels(tenantId, id),
    enabled: Boolean(tenantId && id),
    queryFn: async () =>
      (await api.get<{ levels: SkillLevel[] }>(`/skills/${id}/levels/`)).data.levels,
  })
}

export function useSkillEdges(id: string) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: keys.edges(tenantId, id),
    enabled: Boolean(tenantId && id),
    queryFn: async () => (await api.get<{ edges: SkillEdge[] }>(`/skills/${id}/edges/`)).data.edges,
  })
}

export function useSkillVersions(id: string) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: keys.versions(tenantId, id),
    enabled: Boolean(tenantId && id),
    queryFn: async () =>
      (await api.get<{ versions: ApiSkill[] }>(`/skills/${id}/versions/`)).data.versions,
  })
}

export function useSkillOverrides() {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: keys.overrides(tenantId),
    enabled: Boolean(tenantId),
    queryFn: async () =>
      (
        await api.get<Paginated<SkillOverride>>('/skills/overrides/', {
          params: { page_size: 200 },
        })
      ).data.results,
  })
}

/** Refresh the catalogue plus everything cached for one skill. */
function useInvalidateSkill() {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return (id?: string) => {
    void qc.invalidateQueries({ queryKey: keys.skills(tenantId) })
    if (id) {
      void qc.invalidateQueries({ queryKey: keys.skill(tenantId, id) })
      void qc.invalidateQueries({ queryKey: keys.versions(tenantId, id) })
    }
  }
}

export function useCreateSkill() {
  const invalidate = useInvalidateSkill()
  return useMutation({
    mutationFn: async (input: SkillInput) => (await api.post<ApiSkill>('/skills/', input)).data,
    onSuccess: () => invalidate(),
  })
}

export function useUpdateSkill(id: string) {
  const invalidate = useInvalidateSkill()
  return useMutation({
    mutationFn: async (input: Partial<SkillInput>) =>
      (await api.patch<ApiSkill>(`/skills/${id}/`, input)).data,
    onSuccess: () => invalidate(id),
  })
}

export function usePublishSkill(id: string) {
  const invalidate = useInvalidateSkill()
  return useMutation({
    mutationFn: async () => (await api.post<ApiSkill>(`/skills/${id}/publish/`)).data,
    onSuccess: () => invalidate(id),
  })
}

export function useRetireSkill(id: string) {
  const invalidate = useInvalidateSkill()
  return useMutation({
    mutationFn: async () => {
      await api.delete(`/skills/${id}/`)
    },
    onSuccess: () => invalidate(id),
  })
}

export function useNewSkillVersion(id: string) {
  const invalidate = useInvalidateSkill()
  return useMutation({
    mutationFn: async () => (await api.post<ApiSkill>(`/skills/${id}/new-version/`)).data,
    onSuccess: () => invalidate(id),
  })
}

export function useReplaceLevels(id: string) {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (levels: SkillLevel[]) =>
      (await api.put<{ levels: SkillLevel[] }>(`/skills/${id}/levels/`, { levels })).data.levels,
    onSuccess: (levels) => qc.setQueryData(keys.levels(tenantId, id), levels),
  })
}

export function useAddEdge(id: string) {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: { to_skill: string; kind: EdgeKind }) =>
      (await api.post<SkillEdge>(`/skills/${id}/edges/`, input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.edges(tenantId, id) }),
  })
}

export function useRemoveEdge(id: string) {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (edgeId: string) => {
      await api.delete(`/skills/${id}/edges/`, { params: { edge: edgeId } })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.edges(tenantId, id) }),
  })
}

export function useOverrideSkill() {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      skillId,
      ...input
    }: {
      skillId: string
      name?: string
      status?: string
      hidden?: boolean
    }) => (await api.post(`/skills/${skillId}/override/`, input)).data,
    onSuccess: (_data, { skillId }) => {
      void qc.invalidateQueries({ queryKey: keys.overrides(tenantId) })
      void qc.invalidateQueries({ queryKey: keys.skills(tenantId) })
      void qc.invalidateQueries({ queryKey: keys.skill(tenantId, skillId) })
    },
  })
}

export function useSaveDomain() {
  const tenantId = useTenantId()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...input }: { id?: string; name: string; sort?: number }) =>
      id
        ? (await api.patch<SkillDomain>(`/skills/domains/${id}/`, input)).data
        : (await api.post<SkillDomain>('/skills/domains/', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.domains(tenantId) }),
  })
}
