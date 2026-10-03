/**
 * The learning library: the learner's resources in progress, then every
 * published resource, filterable by skill and kind. Reading needs directory.view;
 * recording progress needs skill.claim.submit.
 */
import { useState } from 'react'

import { useAuth } from '../../lib/auth'
import { useSkills } from '../skills/api'
import { useMyProgress, useResources } from './api'
import { LearningTabs } from './components/LearningTabs'
import { ResourceCard } from './components/ResourceCard'
import { SkillChips } from './components/SkillChips'
import { KIND_LABELS, RESOURCE_KINDS } from './types'
import { useProgressActions } from './useProgressActions'

const SELECT =
  'ml-2 rounded-md border border-brand-100 bg-white px-2 py-1 text-sm font-normal normal-case tracking-normal text-ink'
const LABEL = 'font-mono text-[11px] uppercase tracking-[0.1em] text-ink-soft'

export function ResourceLibrary() {
  const { hasCapability } = useAuth()
  const canLearn = hasCapability('skill.claim.submit')

  const [skill, setSkill] = useState('')
  const [kind, setKind] = useState('')
  const skills = useSkills()
  const resources = useResources({ skill, kind })
  const progress = useMyProgress(canLearn)
  const actions = useProgressActions()

  const progressByResource = new Map((progress.data ?? []).map((p) => [p.resource, p]))
  const active = (progress.data ?? []).filter((p) => p.status === 'in_progress')
  const completed = (progress.data ?? []).filter((p) => p.status === 'completed').length

  return (
    <section className="mx-auto max-w-3xl">
      <LearningTabs />

      {canLearn && (
        <div className="mt-6">
          <h2 className="text-sm font-semibold text-ink">Your learning</h2>
          <p className="mt-0.5 text-[12px] text-ink-soft">
            {active.length} in progress · {completed} completed
          </p>
          {active.length > 0 && (
            <div className="mt-3 grid gap-2 sm:grid-cols-2">
              {active.map((p) => (
                <ResourceCard
                  key={p.id}
                  resource={p.resource_detail}
                  progress={p}
                  canLearn
                  busy={actions.busy}
                  onStart={() => actions.start(p.resource)}
                  onModuleDone={actions.markModuleDone}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <div className="mt-8 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink">Library</h2>
        <div className="flex flex-wrap gap-4">
          <label className={LABEL}>
            Skill
            <select value={skill} onChange={(e) => setSkill(e.target.value)} className={SELECT}>
              <option value="">All skills</option>
              {(skills.data ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className={LABEL}>
            Kind
            <select value={kind} onChange={(e) => setKind(e.target.value)} className={SELECT}>
              <option value="">All kinds</option>
              {RESOURCE_KINDS.map((k) => (
                <option key={k} value={k}>
                  {KIND_LABELS[k]}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>

      {resources.isLoading && <p className="mt-4 text-ink-soft">Loading resources…</p>}
      {resources.isError && <p className="mt-4 text-ink-soft">Could not load the library.</p>}
      {resources.data && resources.data.length === 0 && (
        <p className="mt-4 text-sm text-ink-soft">No resources match these filters.</p>
      )}
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        {(resources.data ?? []).map((r) => (
          <ResourceCard
            key={r.id}
            resource={r}
            progress={progressByResource.get(r.id)}
            canLearn={canLearn}
            busy={actions.busy}
            onStart={() => actions.start(r.id)}
            onModuleDone={actions.markModuleDone}
          >
            <SkillChips links={r.skills} />
          </ResourceCard>
        ))}
      </div>
    </section>
  )
}
