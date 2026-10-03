/**
 * Learner profile: who someone is, where they sit, what they claim and what has
 * been verified. Verified skills are the tier readiness reads; declared skills
 * are self-reported and labelled as such.
 */
import { Link } from 'react-router-dom'

import { apiErrorMessage } from '../../lib/errors'
import { LevelMeter } from '../roadmap/components/LevelMeter'
import type { LevelValue } from '../roadmap/types'
import { LEVEL_LABELS } from '../skills/types'
import { usePersonProfile } from './usePersonProfile'

function asLevel(level: number | null): LevelValue {
  return Math.max(0, Math.min(4, level ?? 0)) as LevelValue
}

function levelLabel(level: number | null): string {
  if (level == null) return '—'
  return LEVEL_LABELS[level] ?? `L${level}`
}

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('')
}

function SkillRow({ name, level, meta }: { name: string; level: number | null; meta?: string }) {
  return (
    <li className="flex items-center justify-between gap-3 py-2">
      <div>
        <div className="text-[13.5px] font-medium text-ink">{name}</div>
        {meta && <div className="text-[12px] text-ink-soft">{meta}</div>}
      </div>
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11px] text-ink-soft">{levelLabel(level)}</span>
        <LevelMeter currentLevel={asLevel(level)} label={name} />
      </div>
    </li>
  )
}

export function PersonProfile({ personId }: { personId: string }) {
  const { data, isLoading, isError, error } = usePersonProfile(personId)

  if (isLoading) return <p className="text-ink-soft">Loading profile…</p>
  if (isError || !data)
    return (
      <p className="mx-auto max-w-md rounded-xl border border-brand-100 bg-white p-6 text-center text-ink-soft">
        Couldn’t load this profile. {apiErrorMessage(error)}
      </p>
    )

  return (
    <section className="mx-auto max-w-3xl space-y-5">
      <Link to="/directory" className="text-[13px] font-semibold text-brand-700 hover:underline">
        ← Directory
      </Link>

      <div className="flex items-center gap-4 rounded-xl border border-brand-100 bg-white p-4">
        <span
          aria-hidden
          className="flex h-12 w-12 items-center justify-center rounded-full text-[15px] font-semibold text-white"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {initials(data.display_name)}
        </span>
        <div>
          <h1 className="text-xl font-bold tracking-tight text-ink">{data.display_name}</h1>
          <p className="text-sm text-ink-soft">
            {data.email} · {data.org_unit?.name ?? 'No org unit'}
          </p>
        </div>
      </div>

      {data.readiness.length > 0 && (
        <div className="rounded-xl border border-brand-100 bg-white p-4">
          <h2 className="text-sm font-semibold text-ink">Readiness</h2>
          <ul className="mt-2 space-y-2">
            {data.readiness.map((r) => (
              <li key={r.job_profile_id}>
                <div className="flex justify-between text-[13px]">
                  <span className="text-ink">{r.job_profile_name}</span>
                  <span className="font-mono text-ink-soft">
                    {r.met}/{r.total} core · {r.readiness_pct}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-brand-50">
                  <div
                    className="h-1.5 rounded-full"
                    style={{
                      width: `${r.readiness_pct}%`,
                      backgroundColor: 'var(--tenant-accent)',
                    }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-brand-100 bg-white p-4">
          <h2 className="text-sm font-semibold text-ink">Verified skills</h2>
          <p className="text-[12px] text-ink-soft">
            Confirmed by a verifier. These count toward readiness.
          </p>
          {data.verified.length === 0 ? (
            <p className="mt-3 text-[13px] text-ink-soft">Nothing verified yet.</p>
          ) : (
            <ul className="mt-1 divide-y divide-brand-50">
              {data.verified.map((v) => (
                <SkillRow
                  key={`${v.skill_id}-${v.verified_at}`}
                  name={v.skill_name}
                  level={v.level}
                  meta={
                    v.verified_at
                      ? `Verified ${new Date(v.verified_at).toLocaleDateString()}`
                      : undefined
                  }
                />
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-xl border border-brand-100 bg-white p-4">
          <h2 className="text-sm font-semibold text-ink">Declared skills</h2>
          <p className="text-[12px] text-ink-soft">Self-reported.</p>
          {data.declared.length === 0 ? (
            <p className="mt-3 text-[13px] text-ink-soft">No skills declared yet.</p>
          ) : (
            <ul className="mt-1 divide-y divide-brand-50">
              {data.declared.map((d) => (
                <SkillRow
                  key={d.skill_id}
                  name={d.skill_name}
                  level={d.level}
                  meta={d.note || undefined}
                />
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  )
}
