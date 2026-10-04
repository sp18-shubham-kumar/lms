import type { Invitation } from '../invitations/types'

/** A tenant as listed to platform operators (GET /api/platform/tenants/). */
export interface PlatformTenant {
  id: string
  name: string
  slug: string
  status: string
  accent_color: string
  created_at: string
  member_count: number
}

/** Body of POST /api/platform/tenants/. */
export interface ProvisionTenantInput {
  name: string
  slug: string
  admin_email: string
}

/** Result of POST /api/platform/tenants/. The invitation carries its accept link once. */
export interface ProvisionedTenant {
  tenant: { id: string; name: string; slug: string }
  admin: { id: string; email: string; display_name: string }
  role: string
  invitation: Invitation
}
