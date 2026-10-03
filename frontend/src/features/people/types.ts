export interface DirectoryPerson {
  id: string
  email: string
  display_name: string
  org_unit: string | null
  status: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

/** Directory filters (GET /api/identity/people/?q=&skill=&level=&org_unit=). */
export interface PeopleFilters {
  q?: string
  skill?: string
  /** Minimum declared level; only applied together with `skill`. */
  level?: number
  org_unit?: string
}

/** GET /api/identity/people/{id}/ (or /people/me/). */
export interface PersonProfile {
  id: string
  email: string
  display_name: string
  status: string
  joined_at: string | null
  org_unit: { id: string; name: string; path: string } | null
  declared: Array<{ skill_id: string; skill_name: string; level: number | null; note: string }>
  verified: Array<{
    skill_id: string
    skill_name: string
    level: number
    verified_at: string | null
  }>
  readiness: Array<{
    job_profile_id: string
    job_profile_name: string
    met: number
    total: number
    readiness_pct: number
    computed_at: string
  }>
}
