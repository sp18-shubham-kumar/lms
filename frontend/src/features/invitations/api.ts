/**
 * Invitation API hooks: list / create / resend / cancel (tenant-scoped, gated by
 * member.invite) and the public accept call.
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../../lib/api'
import { useTenant } from '../../lib/tenant'
import type { Paginated } from '../people/types'
import type { AcceptedInvitation, AcceptInvitationInput, Invitation } from './types'

export function usePendingInvitations() {
  const { tenant } = useTenant()
  return useQuery({
    queryKey: ['invitations', tenant?.id],
    enabled: Boolean(tenant?.id),
    queryFn: async () => {
      const resp = await api.get<Paginated<Invitation>>('/identity/invitations/', {
        params: { page_size: 200 },
      })
      return resp.data.results
    },
  })
}

/** Shared by create / resend / cancel: each changes the pending list. */
function useInvitationMutation<TInput, TResult>(fn: (input: TInput) => Promise<TResult>) {
  const { tenant } = useTenant()
  const qc = useQueryClient()
  return useMutation({
    mutationFn: fn,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['invitations', tenant?.id] }),
  })
}

export function useCreateInvitation() {
  return useInvitationMutation(
    async (input: { email: string; role: string }) =>
      (await api.post<Invitation>('/identity/invitations/', input)).data,
  )
}

export function useResendInvitation() {
  return useInvitationMutation(
    async (id: string) => (await api.post<Invitation>(`/identity/invitations/${id}/resend/`)).data,
  )
}

export function useCancelInvitation() {
  return useInvitationMutation(async (id: string) => {
    await api.delete(`/identity/invitations/${id}/`)
  })
}

/** Public: no JWT or tenant needed. Sets the password and opens the membership. */
export function useAcceptInvitation() {
  return useMutation({
    mutationFn: async (input: AcceptInvitationInput) =>
      (await api.post<AcceptedInvitation>('/auth/invitations/accept/', input)).data,
  })
}
