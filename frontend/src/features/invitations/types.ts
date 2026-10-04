/** An invitation (GET/POST /api/identity/invitations/). */
export interface Invitation {
  id: string
  email: string
  role: string
  role_id: string | null
  status: 'pending' | 'accepted' | 'cancelled'
  expires_at: string
  /** Only on create/resend: the raw token and its accept link, shown once. */
  token?: string
  invite_url?: string
}

/** Body of POST /api/auth/invitations/accept/. */
export interface AcceptInvitationInput {
  token: string
  password: string
}

export interface AcceptedInvitation {
  email: string
  tenant_id: string
}
