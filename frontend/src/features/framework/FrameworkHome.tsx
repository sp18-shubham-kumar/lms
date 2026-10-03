/**
 * Skill framework authoring home: the tenant's catalogue grouped by domain, with
 * "New skill", tenant domain management, and a way back to hidden global skills.
 *
 * The API returns one row per skill *version*; a skill is identified across
 * versions by (owner, slug), so the list shows only the latest version of each.
 */
import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { apiErrorMessage } from '../../lib/errors'
import { useSkillDomains, useSkills } from '../skills/api'
import type { SkillDomain } from '../skills/types'
import { useCreateSkill, useOverrideSkill, useSaveDomain, useSkillOverrides } from './api'
import { SkillChips } from './components/StatusBadge'
import { SkillForm } from './components/SkillForm'
import { latestVersions, type SkillStatus } from './types'

type StatusFilter = 'all' | SkillStatus

const INPUT = 'rounded-md border border-brand-100 bg-white px-2.5 py-1.5 text-[13px] text-ink'

export function FrameworkHome() {
  const navigate = useNavigate()
  const skills = useSkills()
  const domains = useSkillDomains()
  const create = useCreateSkill()
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState<StatusFilter>('all')
  const [creating, setCreating] = useState(false)

  const shown = useMemo(() => {
    const q = query.trim().toLowerCase()
    return latestVersions(skills.data ?? []).filter(
      (s) =>
        (status === 'all' || s.status === status) &&
        (!q || s.name.toLowerCase().includes(q) || s.slug.includes(q)),
    )
  }, [skills.data, query, status])

  if (skills.isLoading || domains.isLoading) {
    return <p className="text-ink-soft">Loading the skill framework…</p>
  }
  if (skills.isError || domains.isError) {
    return <p className="text-red-600">Couldn’t load the skill framework.</p>
  }

  const domainList = domains.data ?? []
  const groups = domainList
    .map((d) => ({ domain: d, skills: shown.filter((s) => s.domain === d.id) }))
    .filter((g) => g.skills.length > 0)

  return (
    <section className="mx-auto max-w-5xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-ink">Skill framework</h1>
          <p className="mt-1 text-sm text-ink-soft">
            Define skills, their level rubrics and prerequisites. Publish a version to make it
            available to learners and verifiers.
          </p>
        </div>
        {!creating && (
          <button
            type="button"
            onClick={() => setCreating(true)}
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            + New skill
          </button>
        )}
      </div>

      {creating && (
        <div className="mt-4 rounded-xl border border-brand-100 bg-white p-4">
          <div className="mb-3 text-[13px] font-semibold text-ink">New skill (draft)</div>
          {domainList.length === 0 ? (
            <p className="text-[13px] text-ink-soft">Add a domain below before creating skills.</p>
          ) : (
            <SkillForm
              domains={domainList}
              submitLabel="Create draft"
              busy={create.isPending}
              error={create.error}
              onCancel={() => setCreating(false)}
              onSubmit={(input) =>
                create.mutate(input, {
                  onSuccess: (skill) => navigate(`/framework/skills/${skill.id}`),
                })
              }
            />
          )}
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-2">
        <input
          type="search"
          aria-label="Search skills"
          placeholder="Search skills…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className={`w-64 ${INPUT}`}
        />
        <select
          aria-label="Status"
          value={status}
          onChange={(e) => setStatus(e.target.value as StatusFilter)}
          className={INPUT}
        >
          <option value="all">All statuses</option>
          <option value="draft">Draft</option>
          <option value="published">Published</option>
          <option value="retired">Retired</option>
        </select>
        <span className="text-[12.5px] text-ink-soft">
          {shown.length} skill{shown.length === 1 ? '' : 's'}
        </span>
      </div>

      <div className="mt-4 space-y-5">
        {groups.length === 0 && <p className="text-ink-soft">No skills match.</p>}
        {groups.map(({ domain, skills: inDomain }) => (
          <div key={domain.id}>
            <h2 className="text-[13px] font-semibold uppercase tracking-wide text-ink-soft">
              {domain.name}
            </h2>
            <ul className="mt-2 divide-y divide-brand-50 rounded-xl border border-brand-100 bg-white">
              {inDomain.map((s) => (
                <li key={s.id}>
                  <Link
                    to={`/framework/skills/${s.id}`}
                    className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-brand-50/50"
                  >
                    <span className="text-[13.5px] font-semibold text-ink">{s.name}</span>
                    <SkillChips skill={s} />
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-2">
        <DomainsPanel domains={domainList} />
        <HiddenSkillsPanel />
      </div>
    </section>
  )
}

/** Add and rename this tenant's domains. Global domains are listed read-only. */
function DomainsPanel({ domains }: { domains: SkillDomain[] }) {
  const save = useSaveDomain()
  const [name, setName] = useState('')
  const [editing, setEditing] = useState<{ id: string; name: string } | null>(null)

  return (
    <div className="rounded-xl border border-brand-100 bg-white p-4">
      <h2 className="text-[13px] font-semibold text-ink">Domains</h2>
      <ul className="mt-2 space-y-1.5 text-[13px]">
        {domains.map((d) => (
          <li key={d.id} className="flex items-center justify-between gap-2">
            {editing?.id === d.id ? (
              <span className="flex flex-1 gap-2">
                <input
                  aria-label={`Rename ${d.name}`}
                  value={editing.name}
                  onChange={(e) => setEditing({ id: d.id, name: e.target.value })}
                  className={`flex-1 ${INPUT}`}
                />
                <button
                  type="button"
                  disabled={save.isPending || !editing.name.trim()}
                  onClick={() =>
                    save.mutate(
                      { id: d.id, name: editing.name.trim() },
                      { onSuccess: () => setEditing(null) },
                    )
                  }
                  className="text-[12.5px] font-semibold text-brand-700 disabled:opacity-50"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setEditing(null)}
                  className="text-[12.5px] text-ink-soft"
                >
                  Cancel
                </button>
              </span>
            ) : (
              <>
                <span className="text-ink">{d.name}</span>
                {d.tenant === null ? (
                  <span className="text-[11px] text-ink-soft">global</span>
                ) : (
                  <button
                    type="button"
                    onClick={() => setEditing({ id: d.id, name: d.name })}
                    className="text-[12.5px] font-semibold text-brand-700"
                  >
                    Rename
                  </button>
                )}
              </>
            )}
          </li>
        ))}
      </ul>
      <form
        className="mt-3 flex gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (!name.trim()) return
          save.mutate({ name: name.trim(), sort: domains.length }, { onSuccess: () => setName('') })
        }}
      >
        <input
          aria-label="New domain name"
          placeholder="New domain…"
          value={name}
          onChange={(e) => setName(e.target.value)}
          className={`flex-1 ${INPUT}`}
        />
        <button
          type="submit"
          disabled={save.isPending || !name.trim()}
          className="rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
        >
          Add domain
        </button>
      </form>
      {save.isError && (
        <p role="alert" className="mt-2 text-[12.5px] text-red-600">
          {apiErrorMessage(save.error, 'Could not save the domain.')}
        </p>
      )}
    </div>
  )
}

/** Hidden global skills drop out of every skill read; this is the way back. */
function HiddenSkillsPanel() {
  const overrides = useSkillOverrides()
  const save = useOverrideSkill()
  const hidden = (overrides.data ?? []).filter((o) => o.hidden)

  return (
    <div className="rounded-xl border border-brand-100 bg-white p-4">
      <h2 className="text-[13px] font-semibold text-ink">Hidden for your organization</h2>
      {overrides.isLoading ? (
        <p className="mt-2 text-[13px] text-ink-soft">Loading…</p>
      ) : hidden.length === 0 ? (
        <p className="mt-2 text-[13px] text-ink-soft">No global skills are hidden.</p>
      ) : (
        <ul className="mt-2 space-y-1.5 text-[13px]">
          {hidden.map((o) => (
            <li key={o.id} className="flex items-center justify-between gap-2">
              <span className="text-ink">{o.name || o.skill_name}</span>
              <button
                type="button"
                disabled={save.isPending}
                onClick={() => save.mutate({ skillId: o.skill, hidden: false })}
                className="text-[12.5px] font-semibold text-brand-700 disabled:opacity-50"
              >
                Unhide
              </button>
            </li>
          ))}
        </ul>
      )}
      {save.isError && (
        <p role="alert" className="mt-2 text-[12.5px] text-red-600">
          {apiErrorMessage(save.error, 'Could not unhide the skill.')}
        </p>
      )}
    </div>
  )
}
