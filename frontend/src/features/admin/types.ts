/** Authz role (GET /api/authz/roles/). */
export interface Role {
  id: string
  name: string
  is_system: boolean
  capabilities: string[]
}

/** One parsed CSV row in a member-import diff. */
export interface ImportRow {
  row: number
  email: string
  display_name: string
  org_unit_path: string
  role: string
  employee_ref: string
}

/** Result of POST /api/identity/members/import/ (dry-run or commit). */
export interface ImportDiff {
  adds: ImportRow[]
  updates: ImportRow[]
  errors: Array<{ row?: number; error?: string } & Record<string, unknown>>
}

/** Seeded capability key (GET /api/authz/capabilities/). */
export interface Capability {
  key: string
}

/** Create/update payload for a role; capabilities replace the role's set. */
export interface RoleInput {
  name: string
  capabilities: string[]
}

/** Grant scope: tenant-wide (`''`) or one org unit. */
export type GrantScopeType = '' | 'org_unit'

/** A role granted to a person (GET /api/authz/grants/). */
export interface RoleGrant {
  id: string
  principal_type: string
  principal_id: string
  role: string
  role_name: string
  scope_type: GrantScopeType
  scope_id: string | null
}

export interface GrantInput {
  principal_id: string
  role: string
  scope_type: GrantScopeType
  scope_id: string | null
}
