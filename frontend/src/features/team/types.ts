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

/** Org unit (GET /api/identity/org-units/). */
export interface OrgUnit {
  id: string
  name: string
  path: string
  parent: string | null
}

/** Heatmap grid (GET /api/profiles/heatmap/). */
export interface HeatmapColumn {
  skill_id: string
  skill_name: string
}
export interface HeatmapRow {
  membership_id: string
  display_name: string
  cells: Array<{ met: boolean }>
}
export interface Heatmap {
  columns: HeatmapColumn[]
  rows: HeatmapRow[]
}
