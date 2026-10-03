/**
 * Learning API hooks (TanStack Query over lib/api.ts).
 *
 * Query keys are tenant-scoped. Progress mutations refresh both the learner's
 * progress list and their recommendations (which embed progress); resource
 * mutations refresh the library.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type {
  LearningProgress,
  LearningResource,
  ProgressStatus,
  Recommendations,
  ResourceFilters,
  ResourceInput,
} from './types'

const RESOURCES_KEY = 'learning-resources'
const PROGRESS_KEY = 'learning-progress'
const RECOMMENDATIONS_KEY = 'learning-recommendations'

export function useResources(filters: ResourceFilters = {}, enabled = true) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: [RESOURCES_KEY, tenant?.id, filters],
    enabled: enabled && Boolean(tenant?.id),
    queryFn: async () => {
      const params: Record<string, string | number> = { page_size: 200 }
      for (const [key, value] of Object.entries(filters)) if (value) params[key] = value
      const resp = await api.get<Paginated<LearningResource>>('/learning/resources/', { params })
      return resp.data.results
    },
  })
}

export function useMyProgress(enabled = true) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: [PROGRESS_KEY, tenant?.id],
    enabled: enabled && Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<LearningProgress>>('/learning/me/progress/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useRecommendations(target: string | null) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: [RECOMMENDATIONS_KEY, tenant?.id, target],
    enabled: Boolean(tenant?.id && target),
    queryFn: async () => {
      const resp = await api.get<Recommendations>('/learning/me/recommendations/', {
        params: { target },
      })
      return resp.data
    },
  })
}

function useInvalidate(...keys: string[]) {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  // Returned so a mutation stays pending until the refetch lands.
  return () => Promise.all(keys.map((key) => qc.invalidateQueries({ queryKey: [key, tenant?.id] })))
}

export function useStartResource() {
  const invalidate = useInvalidate(PROGRESS_KEY, RECOMMENDATIONS_KEY)
  return useMutation({
    mutationFn: async (resourceId: string) => {
      const resp = await api.post<LearningProgress>('/learning/me/progress/', {
        resource: resourceId,
      })
      return resp.data
    },
    onSuccess: invalidate,
  })
}

export function useUpdateProgress() {
  const invalidate = useInvalidate(PROGRESS_KEY, RECOMMENDATIONS_KEY)
  return useMutation({
    mutationFn: async (input: {
      id: string
      completed_modules?: number
      status?: ProgressStatus
    }) => {
      const { id, ...body } = input
      const resp = await api.patch<LearningProgress>(`/learning/me/progress/${id}/`, body)
      return resp.data
    },
    onSuccess: invalidate,
  })
}

export function useCreateResource() {
  const invalidate = useInvalidate(RESOURCES_KEY, RECOMMENDATIONS_KEY)
  return useMutation({
    mutationFn: async (input: ResourceInput) => {
      const resp = await api.post<LearningResource>('/learning/resources/', input)
      return resp.data
    },
    onSuccess: invalidate,
  })
}

export function useUpdateResource() {
  const invalidate = useInvalidate(RESOURCES_KEY, RECOMMENDATIONS_KEY)
  return useMutation({
    mutationFn: async ({ id, ...input }: ResourceInput & { id: string }) => {
      const resp = await api.patch<LearningResource>(`/learning/resources/${id}/`, input)
      return resp.data
    },
    onSuccess: invalidate,
  })
}

export function useArchiveResource() {
  const invalidate = useInvalidate(RESOURCES_KEY, RECOMMENDATIONS_KEY)
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/learning/resources/${id}/`)
    },
    onSuccess: invalidate,
  })
}
