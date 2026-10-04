/**
 * Manager view: team readiness across the tenant (GET /profiles/readiness/),
 * plus the members × skills heatmap (GET /profiles/heatmap/).
 */
import { Link } from 'react-router-dom'

import { useAllJobProfiles } from '../career-paths/api'
import { TeamHeatmap } from './TeamHeatmap'
import { useTeamReadiness } from './api'
import { memberReadinessPath } from './memberLink'

export function TeamReadiness() {
  const { data, isLoading, isError } = useTeamReadiness()
  // Snapshots carry only the profile id; name them from the profile list.
  const profiles = useAllJobProfiles()
  const profileTitle = (id: string) => profiles.data?.find((p) => p.id === id)?.title

  if (isLoading) return <p className="text-ink-soft">Loading team readiness…</p>
  if (isError) return <p className="text-ink-soft">Could not load team readiness.</p>

  const rows = data ?? []

  return (
    <section className="mx-auto max-w-2xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">Team readiness</h1>
      <p className="mt-1 text-sm text-ink-soft">
        {rows.length} readiness snapshot{rows.length === 1 ? '' : 's'} (one per member × target
        grade).
      </p>

      {rows.length === 0 ? (
        <p className="mt-5 rounded-xl border border-brand-100 bg-white p-5 text-sm text-ink-soft">
          No readiness snapshots in this tenant yet. They appear once members have a target grade
          and verified skills.
        </p>
      ) : (
        <ul className="mt-5 space-y-2.5">
          {rows.map((r) => {
            const pct = r.total > 0 ? Math.round((r.met / r.total) * 100) : 0
            return (
              <li key={r.id} className="flex items-center gap-3">
                <Link
                  to={memberReadinessPath(r.membership, r.job_profile)}
                  className="w-40 truncate font-medium text-ink hover:underline"
                >
                  {r.display_name}
                </Link>
                <span className="w-40 truncate text-[12.5px] text-ink-soft">
                  {profileTitle(r.job_profile) ?? 'Job profile'} · v{r.job_profile_version}
                </span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-brand-100">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${pct}%`, backgroundColor: 'var(--tenant-accent)' }}
                  />
                </div>
                <span className="w-20 text-right font-mono text-xs tabular-nums text-ink-soft">
                  {r.met}/{r.total} · {pct}%
                </span>
              </li>
            )
          })}
        </ul>
      )}

      <TeamHeatmap />
    </section>
  )
}
