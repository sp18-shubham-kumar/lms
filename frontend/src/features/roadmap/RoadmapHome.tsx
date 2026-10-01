/**
 * The learner's "My path": readiness toward a target job profile, drawn as a
 * route. Wired to GET /profiles/me/readiness/.
 *
 * Target selection uses GET /profiles/job-profiles/, which currently requires
 * `jobprofile.edit` — so learners without it see guidance instead of a picker
 * (a backend gap flagged to the team).
 */
import { useState } from 'react'

import { useAuth } from '../../lib/auth'
import { useJobProfiles, useReadiness } from './api'
import { RoadmapSpine } from './components/RoadmapSpine'
import { ReadinessRing } from './components/ReadinessRing'
import type { LevelValue, Readiness, RoadmapStep } from './types'

/** Transform the API readiness payload into the roadmap UI model. */
function toSteps(readiness: Readiness): RoadmapStep[] {
  let currentAssigned = false
  return readiness.requirements.map((r) => {
    const met = r.status === 'met'
    let status: RoadmapStep['status']
    if (met) {
      status = 'cleared'
    } else if (!currentAssigned) {
      status = 'current'
      currentAssigned = true
    } else {
      status = 'upcoming'
    }
    const currentLevel = Math.max(0, Math.min(4, r.current_level ?? 0)) as LevelValue
    const targetLevel = Math.max(1, Math.min(4, r.min_level)) as LevelValue
    return {
      id: r.skill_id,
      skill: r.skill_name,
      targetLevel,
      currentLevel,
      status,
      levelsToGo: status === 'current' ? Math.max(1, targetLevel - currentLevel) : undefined,
      note: met
        ? `Cleared · ${r.criticality}`
        : status === 'upcoming'
          ? `${r.criticality} · min ${r.min_level}`
          : undefined,
    }
  })
}

export function RoadmapHome() {
  const { hasCapability } = useAuth()
  const canPickTarget = hasCapability('jobprofile.edit')

  const profiles = useJobProfiles(canPickTarget)
  const [target, setTarget] = useState<string | null>(null)
  const readiness = useReadiness(target)

  const selectedProfile = profiles.data?.find((p) => p.id === target)

  return (
    <section className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-soft">
            Your route to
          </p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink">
            {selectedProfile ? selectedProfile.title : 'a target grade'}
          </h1>
          {readiness.data && (
            <p className="mt-1 text-sm text-ink-soft">
              {readiness.data.met} of {readiness.data.total} core requirements met
            </p>
          )}
        </div>
        {readiness.data && <ReadinessRing value={readiness.data.readiness_pct} />}
      </div>

      {/* Target picker (only for users who can list profiles) */}
      {canPickTarget && (
        <div className="mt-5">
          <label className="font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft">
            Target grade{' '}
            <select
              value={target ?? ''}
              onChange={(e) => setTarget(e.target.value || null)}
              className="ml-2 rounded-md border border-brand-100 bg-white px-2 py-1 text-sm font-normal normal-case tracking-normal text-ink"
            >
              <option value="">Choose a job profile…</option>
              {(profiles.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.title}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {!canPickTarget && (
        <div className="mt-5 rounded-xl border border-brand-100 bg-white p-5 text-sm text-ink-soft">
          Your target grade hasn’t been shared with your account yet. Once a manager sets it,
          your readiness route appears here. In the meantime, declare your skills on the{' '}
          <span className="font-semibold text-ink">Skills</span> page.
        </div>
      )}

      {readiness.isLoading && <p className="mt-5 text-ink-soft">Calculating readiness…</p>}
      {readiness.data && <RoadmapSpine steps={toSteps(readiness.data)} />}
    </section>
  )
}
