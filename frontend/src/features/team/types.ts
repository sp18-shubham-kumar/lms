/** Team readiness snapshot (GET /api/profiles/readiness/). */
export interface ReadinessSnapshot {
  id: string
  membership: string
  job_profile: string
  met: number
  total: number
  blocking_skill_ids: string[]
  job_profile_version: number
  computed_at: string
  display_name: string
}
