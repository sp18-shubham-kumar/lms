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
