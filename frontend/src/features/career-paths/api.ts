/**
 * Career-path authoring hooks: tracks, job profiles (grades), their skill
 * requirements, and the publish / new-version lifecycle.
 *
 * Reads need `directory.view`; every write needs `jobprofile.edit`. Published
 * profiles are immutable server-side (409) — edits go through a new draft.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { Criticality, JobProfile, ProfileRequirement, SkillLevel, Track } from './types'

const PAGE = { page_size: 200 }

function useTenantId() {
  return useTenant().tenant?.id
}

// --- Tracks ------------------------------------------------------------------

export function useTracks() {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: ['tracks', tenantId],
    enabled: Boolean(tenantId),
    queryFn: async () => {
      const resp = await api.get<Paginated<Track>>('/profiles/tracks/', { params: PAGE })
      return resp.data.results
    },
  })
}

function useInvalidateTracks() {
  const qc = useQueryClient()
  const tenantId = useTenantId()
  return () => qc.invalidateQueries({ queryKey: ['tracks', tenantId] })
}

export function useCreateTrack() {
  const invalidate = useInvalidateTracks()
  return useMutation({
    mutationFn: async (name: string) => (await api.post<Track>('/profiles/tracks/', { name })).data,
    onSuccess: invalidate,
  })
}

export function useRenameTrack() {
  const invalidate = useInvalidateTracks()
  return useMutation({
    mutationFn: async ({ id, name }: { id: string; name: string }) =>
      (await api.patch<Track>(`/profiles/tracks/${id}/`, { name })).data,
    onSuccess: invalidate,
  })
}

export function useDeleteTrack() {
  const invalidate = useInvalidateTracks()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/profiles/tracks/${id}/`)
    },
    onSuccess: invalidate,
  })
}

// --- Job profiles --------------------------------------------------------------

/** Every version of every profile, any status — the authoring view. */
export function useAllJobProfiles() {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: ['job-profiles', tenantId, 'all'],
    enabled: Boolean(tenantId),
    queryFn: async () => {
      const resp = await api.get<Paginated<JobProfile>>('/profiles/job-profiles/', {
        params: PAGE,
      })
      return resp.data.results
    },
  })
}

export function useJobProfile(id: string | undefined) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: ['job-profile', tenantId, id],
    enabled: Boolean(tenantId && id),
    queryFn: async () => (await api.get<JobProfile>(`/profiles/job-profiles/${id}/`)).data,
  })
}

/**
 * After any profile write, refresh the profile lists (authoring and target
 * pickers share the `job-profiles` prefix) and the one profile that changed.
 */
function useInvalidateProfile() {
  const qc = useQueryClient()
  const tenantId = useTenantId()
  return (profile: JobProfile) => {
    qc.setQueryData(['job-profile', tenantId, profile.id], profile)
    return qc.invalidateQueries({ queryKey: ['job-profiles', tenantId] })
  }
}

export interface ProfileDraft {
  track: string
  grade: number
  title: string
}

export function useCreateJobProfile() {
  const invalidate = useInvalidateProfile()
  return useMutation({
    mutationFn: async (draft: ProfileDraft) =>
      (await api.post<JobProfile>('/profiles/job-profiles/', draft)).data,
    onSuccess: invalidate,
  })
}

export function useUpdateJobProfile(id: string) {
  const invalidate = useInvalidateProfile()
  return useMutation({
    mutationFn: async (changes: Partial<Pick<JobProfile, 'grade' | 'title'>>) =>
      (await api.patch<JobProfile>(`/profiles/job-profiles/${id}/`, changes)).data,
    onSuccess: invalidate,
  })
}

export function usePublishJobProfile(id: string) {
  const invalidate = useInvalidateProfile()
  return useMutation({
    mutationFn: async () =>
      (await api.post<JobProfile>(`/profiles/job-profiles/${id}/publish/`)).data,
    onSuccess: invalidate,
  })
}

/** Open the next draft of a published profile; requirements are copied over. */
export function useNewProfileVersion(id: string) {
  const invalidate = useInvalidateProfile()
  return useMutation({
    mutationFn: async () =>
      (await api.post<JobProfile>(`/profiles/job-profiles/${id}/new-version/`)).data,
    onSuccess: invalidate,
  })
}

/** DELETE retires the profile (soft); readiness snapshots pinned to it remain. */
export function useRetireJobProfile(id: string) {
  const qc = useQueryClient()
  const tenantId = useTenantId()
  return useMutation({
    mutationFn: async () => {
      await api.delete(`/profiles/job-profiles/${id}/`)
    },
    onSuccess: () =>
      Promise.all([
        qc.invalidateQueries({ queryKey: ['job-profile', tenantId, id] }),
        qc.invalidateQueries({ queryKey: ['job-profiles', tenantId] }),
      ]),
  })
}

// --- Requirements --------------------------------------------------------------

export function useRequirements(profileId: string | undefined) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: ['profile-requirements', tenantId, profileId],
    enabled: Boolean(tenantId && profileId),
    queryFn: async () =>
      (await api.get<ProfileRequirement[]>(`/profiles/job-profiles/${profileId}/requirements/`))
        .data,
  })
}

function useInvalidateRequirements(profileId: string) {
  const qc = useQueryClient()
  const tenantId = useTenantId()
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ['profile-requirements', tenantId, profileId] }),
      // Readiness against this profile changes with its requirements.
      qc.invalidateQueries({ queryKey: ['readiness', tenantId, profileId] }),
    ])
}

export interface RequirementDraft {
  skill: string
  min_level: number
  criticality: Criticality
}

export function useAddRequirement(profileId: string) {
  const invalidate = useInvalidateRequirements(profileId)
  return useMutation({
    mutationFn: async (draft: RequirementDraft) =>
      (
        await api.post<ProfileRequirement>(
          `/profiles/job-profiles/${profileId}/requirements/`,
          draft,
        )
      ).data,
    onSuccess: invalidate,
  })
}

export function useRemoveRequirement(profileId: string) {
  const invalidate = useInvalidateRequirements(profileId)
  return useMutation({
    mutationFn: async (requirementId: string) => {
      await api.delete(`/profiles/job-profiles/${profileId}/requirements/${requirementId}/`)
    },
    onSuccess: invalidate,
  })
}

/** A skill's rubric, so the level picker can name each level. */
export function useSkillLevels(skillId: string | null) {
  const tenantId = useTenantId()
  return useQuery({
    queryKey: ['skill-levels', tenantId, skillId],
    enabled: Boolean(tenantId && skillId),
    queryFn: async () =>
      (await api.get<{ levels: SkillLevel[] }>(`/skills/${skillId}/levels/`)).data.levels,
  })
}
