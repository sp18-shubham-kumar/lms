/**
 * One skill's authoring page. The rubric is the primary content (read by learners
 * to aim and by verifiers to sign off), so it is the first tab.
 *
 * Lifecycle: a tenant draft is edited in place and then published. A published
 * version is immutable, so changing it means starting a new draft version.
 * Global skills can't be edited, only customized for this organization.
 */
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { ConfirmAction } from '../../components/ConfirmAction'
import { apiErrorMessage } from '../../lib/errors'
import { useSkillDomains, useSkills } from '../skills/api'
import {
  useNewSkillVersion,
  usePublishSkill,
  useRetireSkill,
  useSkill,
  useSkillLevels,
  useSkillVersions,
  useUpdateSkill,
} from './api'
import { OverridePanel } from './components/OverridePanel'
import { PrerequisitesEditor } from './components/PrerequisitesEditor'
import { RubricGrid } from './components/RubricGrid'
import { SkillForm } from './components/SkillForm'
import { SkillChips, StatusBadge } from './components/StatusBadge'
import { isEditable, isGlobal } from './types'

type Tab = 'rubric' | 'definition' | 'links' | 'versions' | 'customize'

export function SkillEditor() {
  const { id = '' } = useParams()
  const navigate = useNavigate()
  const skill = useSkill(id)
  const levels = useSkillLevels(id)
  const versions = useSkillVersions(id)
  const catalogue = useSkills()
  const domains = useSkillDomains()
  const update = useUpdateSkill(id)
  const publish = usePublishSkill(id)
  const retire = useRetireSkill(id)
  const newVersion = useNewSkillVersion(id)
  const [tab, setTab] = useState<Tab>('rubric')

  if (skill.isLoading) return <p className="text-ink-soft">Loading skill…</p>
  if (skill.isError || !skill.data) {
    return (
      <section className="mx-auto max-w-4xl">
        <p className="text-ink-soft">This skill isn’t available.</p>
        <Link to="/framework" className="mt-2 inline-block text-sm font-semibold text-brand-700">
          ← Back to the framework
        </Link>
      </section>
    )
  }

  const s = skill.data
  const global = isGlobal(s)
  const editable = isEditable(s)
  const actionError = publish.error ?? retire.error ?? newVersion.error
  const busy = publish.isPending || retire.isPending || newVersion.isPending
  const domainName = domains.data?.find((d) => d.id === s.domain)?.name ?? '—'

  const readOnlyReason = global
    ? 'Global rubrics are maintained by the platform.'
    : s.status === 'published'
      ? 'Published versions are locked. Start a new version to change the rubric.'
      : s.status === 'retired'
        ? 'This skill is retired.'
        : undefined

  const tabs: { key: Tab; label: string }[] = [
    { key: 'rubric', label: 'Rubric' },
    { key: 'definition', label: 'Definition' },
    { key: 'links', label: 'Prerequisites' },
    { key: 'versions', label: 'Versions' },
    ...(global ? [{ key: 'customize' as Tab, label: 'Customize' }] : []),
  ]

  return (
    <section className="mx-auto max-w-5xl">
      <Link to="/framework" className="text-[12.5px] font-semibold text-brand-700">
        ← Skill framework
      </Link>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">{s.name}</h1>
          <div className="mt-1 flex items-center gap-2 text-[12.5px] text-ink-soft">
            <span>{domainName}</span>
            <span className="text-brand-200">·</span>
            <SkillChips skill={s} />
          </div>
          {s.description && <p className="mt-2 max-w-2xl text-sm text-ink-soft">{s.description}</p>}
        </div>

        {!global && (
          <div className="flex flex-wrap items-center gap-2">
            {s.status === 'draft' && (
              <ConfirmAction
                label="Publish"
                prompt={`Publish v${s.version}? It becomes read-only.`}
                confirmLabel="Publish"
                tone="accent"
                busy={busy}
                onConfirm={() => publish.mutate()}
              />
            )}
            {s.status === 'published' && (
              <ConfirmAction
                label="Start new version"
                prompt={`Create draft v${s.version + 1} from this version?`}
                confirmLabel="Create draft"
                tone="accent"
                busy={busy}
                onConfirm={() =>
                  newVersion.mutate(undefined, {
                    onSuccess: (draft) => navigate(`/framework/skills/${draft.id}`),
                  })
                }
              />
            )}
            {s.status !== 'retired' && (
              <ConfirmAction
                label="Retire"
                prompt="Retire this skill? Existing verifications are kept."
                confirmLabel="Retire"
                tone="danger"
                busy={busy}
                onConfirm={() => retire.mutate()}
              />
            )}
          </div>
        )}
      </div>
      {actionError != null && (
        <p role="alert" className="mt-2 text-[12.5px] text-red-600">
          {apiErrorMessage(actionError)}
        </p>
      )}

      <div role="tablist" className="mt-5 flex gap-1 border-b border-brand-100">
        {tabs.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={tab === t.key}
            onClick={() => setTab(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold ${
              tab === t.key ? 'text-ink' : 'border-transparent text-ink-soft hover:text-ink'
            }`}
            style={tab === t.key ? { borderColor: 'var(--tenant-accent)' } : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {tab === 'rubric' &&
          (levels.isLoading ? (
            <p className="text-ink-soft">Loading rubric…</p>
          ) : (
            <RubricGrid
              key={`${s.id}:${s.status}`}
              skillId={s.id}
              levels={levels.data ?? []}
              editable={editable}
              readOnlyReason={readOnlyReason}
            />
          ))}

        {tab === 'definition' &&
          (editable && domains.data ? (
            <div className="rounded-xl border border-brand-100 bg-white p-4">
              <SkillForm
                key={s.id}
                domains={domains.data}
                initial={{
                  domain: s.domain,
                  name: s.name,
                  slug: s.slug,
                  external_code: s.external_code,
                  description: s.description,
                }}
                lockSlug
                submitLabel="Save definition"
                busy={update.isPending}
                error={update.error}
                onSubmit={({ slug: _slug, ...input }) => update.mutate(input)}
              />
              {update.isSuccess && <p className="mt-2 text-[12.5px] text-brand-700">Saved ✓</p>}
            </div>
          ) : (
            <dl className="grid gap-3 rounded-xl border border-brand-100 bg-white p-4 text-[13px] sm:grid-cols-2">
              {[
                ['Name', s.name],
                ['Slug', s.slug],
                ['Domain', domainName],
                ['External code', s.external_code || '—'],
                ['Description', s.description || '—'],
              ].map(([label, value]) => (
                <div key={label}>
                  <dt className="text-[11px] font-semibold uppercase tracking-wide text-ink-soft">
                    {label}
                  </dt>
                  <dd className="mt-0.5 text-ink">{value}</dd>
                </div>
              ))}
              {readOnlyReason && (
                <p className="text-[12.5px] text-ink-soft sm:col-span-2">
                  {readOnlyReason.replace('the rubric', 'the definition')}
                </p>
              )}
            </dl>
          ))}

        {tab === 'links' && (
          <PrerequisitesEditor skill={s} catalogue={catalogue.data ?? []} editable={!global} />
        )}

        {tab === 'versions' && (
          <ul className="divide-y divide-brand-50 rounded-xl border border-brand-100 bg-white">
            {(versions.data ?? []).map((v) => (
              <li key={v.id} className="flex items-center justify-between px-4 py-2.5 text-[13px]">
                <span className="flex items-center gap-2">
                  <span className="font-mono font-semibold text-ink">v{v.version}</span>
                  <StatusBadge status={v.status} />
                  {v.id === s.id && <span className="text-[12px] text-ink-soft">(viewing)</span>}
                </span>
                {v.id !== s.id && (
                  <Link
                    to={`/framework/skills/${v.id}`}
                    className="text-[12.5px] font-semibold text-brand-700"
                  >
                    Open
                  </Link>
                )}
              </li>
            ))}
          </ul>
        )}

        {tab === 'customize' && global && (
          <OverridePanel skill={s} onHidden={() => navigate('/framework')} />
        )}
      </div>
    </section>
  )
}
