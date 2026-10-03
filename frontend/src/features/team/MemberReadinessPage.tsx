/**
 * Manager view of one member's readiness (P2-R7): the same route the learner
 * sees on "My path", for a target the manager picks. Reached from the team
 * heatmap and snapshot list; the target rides in `?target=` so links are shareable.
 */
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { useAuth } from '../../lib/auth'
import { apiErrorMessage } from '../../lib/apiError'
import { useJobProfiles } from '../roadmap/api'
import { ReadinessRing } from '../roadmap/components/ReadinessRing'
import { RoadmapSpine } from '../roadmap/components/RoadmapSpine'
import { toSteps } from '../roadmap/steps'
import { useMemberReadiness } from './api'

export function MemberReadinessPage() {
  const { membershipId } = useParams<{ membershipId: string }>()
  const [params, setParams] = useSearchParams()
  const { hasCapability } = useAuth()
  const canView = hasCapability('report.org.view')

  const profiles = useJobProfiles(canView)
  const target = params.get('target') ?? profiles.data?.[0]?.id ?? null
  const readiness = useMemberReadiness(canView ? membershipId : undefined, target)

  if (!canView) {
    return (
      <section className="mx-auto max-w-2xl">
        <p className="rounded-xl border border-brand-100 bg-white p-5 text-sm text-ink-soft">
          Viewing a team member’s readiness needs the{' '}
          <span className="font-mono">report.org.view</span> capability.
        </p>
      </section>
    )
  }

  const selected = profiles.data?.find((p) => p.id === target)

  return (
    <section className="mx-auto max-w-2xl">
      <Link to="/team" className="text-[13px] text-brand-700 hover:underline">
        ← Team readiness
      </Link>
      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-soft">
            {readiness.data?.display_name ?? 'Team member'} · route to
          </p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink">
            {selected ? selected.title : 'a target grade'}
          </h1>
          {readiness.data && (
            <p className="mt-1 text-sm text-ink-soft">
              {readiness.data.met} of {readiness.data.total} core requirements met
            </p>
          )}
        </div>
        {readiness.data && <ReadinessRing value={readiness.data.readiness_pct} />}
      </div>

      <div className="mt-5">
        <label className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft">
          Target grade{' '}
          <select
            value={target ?? ''}
            onChange={(e) => setParams(e.target.value ? { target: e.target.value } : {})}
            className="ml-2 rounded-md border border-brand-100 bg-white px-2 py-1 text-sm font-normal normal-case tracking-normal text-ink"
          >
            {!target && <option value="">Choose a job profile…</option>}
            {(profiles.data ?? []).map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </select>
        </label>
      </div>

      {profiles.data?.length === 0 && (
        <p className="mt-5 text-ink-soft">No published job profiles to measure against yet.</p>
      )}
      {readiness.isLoading && <p className="mt-5 text-ink-soft">Calculating readiness…</p>}
      {readiness.isError && (
        <p className="mt-5 text-ink-soft">
          {apiErrorMessage(readiness.error, 'Could not load readiness for this member.')}
        </p>
      )}
      {readiness.data && <RoadmapSpine steps={toSteps(readiness.data)} />}
    </section>
  )
}
