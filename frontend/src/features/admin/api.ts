/** Admin API hooks: roles, capabilities, grants, offboarding and member import. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { Capability, GrantInput, ImportDiff, Role, RoleGrant, RoleInput } from './types'

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

export function useCapabilities() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['capabilities', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Capability[]>('/authz/capabilities/')
      return resp.data.map((c) => c.key)
    },
  })
}

/** Create a role (no id) or update one (with id). */
export function useSaveRole() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...input }: RoleInput & { id?: string }) => {
      const resp = id
        ? await api.patch<Role>(`/authz/roles/${id}/`, input)
        : await api.post<Role>('/authz/roles/', input)
      return resp.data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles', tenant?.id] }),
  })
}

export function useDeleteRole() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: string) => {
      await api.delete(`/authz/roles/${id}/`)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['roles', tenant?.id] }),
  })
}

export function useGrants(principalId: string | null) {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['grants', tenant?.id, principalId],
    enabled: Boolean(tenant?.id && principalId),
    queryFn: async () => {
      const resp = await api.get<Paginated<RoleGrant>>('/authz/grants/', {
        params: { principal_id: principalId, page_size: 200 },
      })
      return resp.data.results
    },
  })
}

export function useCreateGrant() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: GrantInput) => {
      const resp = await api.post<RoleGrant>('/authz/grants/', input)
      return resp.data
    },
    onSuccess: (grant) =>
      qc.invalidateQueries({ queryKey: ['grants', tenant?.id, grant.principal_id] }),
  })
}

export function useRevokeGrant() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (grant: RoleGrant) => {
      await api.delete(`/authz/grants/${grant.id}/`)
      return grant
    },
    onSuccess: (grant) =>
      qc.invalidateQueries({ queryKey: ['grants', tenant?.id, grant.principal_id] }),
  })
}

/** End a membership: hides the person and revokes their grants in this tenant. */
export function useOffboardMember() {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (personId: string) => {
      await api.post(`/identity/people/${personId}/offboard/`)
      return personId
    },
    onSuccess: (personId) => {
      qc.invalidateQueries({ queryKey: ['people', tenant?.id] })
      qc.invalidateQueries({ queryKey: ['grants', tenant?.id, personId] })
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
