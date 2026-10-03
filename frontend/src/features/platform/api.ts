/**
 * Platform-operator API hooks. These endpoints are not tenant-scoped: the request
 * interceptor may still attach X-Tenant-Id, which the platform views ignore.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import type { PlatformTenant, ProvisionedTenant, ProvisionTenantInput } from './types'

const TENANTS_KEY = ['platform', 'tenants']

export function usePlatformTenants() {
  return useQuery({
    queryKey: TENANTS_KEY,
    queryFn: async () => (await api.get<PlatformTenant[]>('/platform/tenants/')).data,
  })
}

export function useProvisionTenant() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (input: ProvisionTenantInput) =>
      (await api.post<ProvisionedTenant>('/platform/tenants/', input)).data,
    onSuccess: () => qc.invalidateQueries({ queryKey: TENANTS_KEY }),
  })
}
