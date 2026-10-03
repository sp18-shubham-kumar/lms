/**
 * One job profile version (/career-paths/:id): its requirements, lifecycle
 * actions and version history (P2-R5, P2-R9).
 *
 * Lifecycle: draft → published (explicit confirm) → retired. A published
 * version is never edited; "Edit as new version" opens the next draft with the
 * requirements copied, and only one draft per grade can be open at a time.
 */
import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { useAuth } from '../../lib/auth'
import { apiErrorMessage } from '../../lib/apiError'
import {
  useAllJobProfiles,
  useJobProfile,
  useNewProfileVersion,
  usePublishJobProfile,
  useRetireJobProfile,
  useTracks,
  useUpdateJobProfile,
} from './api'
import { RequirementsEditor } from './components/RequirementsEditor'
import { ProfileStatusBadge } from './components/StatusBadge'
import {
  CARD,
  INPUT,
  LABEL,
  PRIMARY_BUTTON,
  PRIMARY_STYLE,
  SECONDARY_BUTTON,
} from './components/styles'
import { groupLineages, lineageKey, type Lineage } from './lineage'
import { EDIT_CAPABILITY, type JobProfile } from './types'

export function JobProfileDetail() {
  const { id } = useParams<{ id: string }>()
  const { hasCapability } = useAuth()
  const profile = useJobProfile(id)
  const all = useAllJobProfiles()
  const tracks = useTracks()

  if (!hasCapability(EDIT_CAPABILITY)) {
    return (
      <section className="mx-auto max-w-2xl">
        <p className={`${CARD} text-sm text-ink-soft`}>
          Editing career paths needs the <span className="font-mono">jobprofile.edit</span>{' '}
          capability.
        </p>
      </section>
    )
  }
  if (profile.isLoading) return <p className="text-ink-soft">Loading job profile…</p>
  if (profile.isError || !profile.data) {
    return <p className="text-ink-soft">Could not load this job profile.</p>
  }

  const p = profile.data
  const lineage = groupLineages(all.data ?? []).find((l) => l.key === lineageKey(p))
  const trackName = tracks.data?.find((t) => t.id === p.track)?.name

  return (
    <section className="mx-auto max-w-3xl">
      <Link to="/career-paths" className="text-[13px] text-brand-700 hover:underline">
        ← Career paths
      </Link>
      <div className="mt-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-bold tracking-tight text-ink">{p.title}</h1>
        <ProfileStatusBadge status={p.status} />
        <span className="font-mono text-[12px] text-ink-soft">v{p.version}</span>
      </div>
      <p className={`mt-1 ${LABEL}`}>
        {trackName ?? 'Track'} · grade {p.grade}
      </p>

      {p.status === 'draft' && <DraftDetails profile={p} />}
      <LifecycleActions profile={p} lineage={lineage} />
      <RequirementsEditor profileId={p.id} editable={p.status === 'draft'} />
      {lineage && <VersionHistory lineage={lineage} currentId={p.id} />}
    </section>
  )
}

/**
 * Title and grade identify a grade across its versions, so they're editable only
 * on a first draft; later versions keep them so history stays in one place.
 */
function DraftDetails({ profile }: { profile: JobProfile }) {
  const [title, setTitle] = useState(profile.title)
  const [grade, setGrade] = useState(String(profile.grade))
  const update = useUpdateJobProfile(profile.id)

  if (profile.version > 1) return null

  const dirty = title.trim() !== profile.title || Number(grade) !== profile.grade
  const submit = (e: FormEvent) => {
    e.preventDefault()
    update.mutate({ title: title.trim(), grade: Number(grade) })
  }

  return (
    <form onSubmit={submit} className={`mt-5 ${CARD} flex flex-wrap items-end gap-3`}>
      <label className={LABEL}>
        Title
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          className={`${INPUT} ml-2 w-64 font-sans normal-case tracking-normal`}
        />
      </label>
      <label className={LABEL}>
        Grade
        <input
          type="number"
          min={1}
          value={grade}
          onChange={(e) => setGrade(e.target.value)}
          className={`${INPUT} ml-2 w-16 font-sans normal-case tracking-normal`}
        />
      </label>
      <button
        type="submit"
        disabled={!dirty || !title.trim() || !grade || update.isPending}
        className={SECONDARY_BUTTON}
      >
        Save details
      </button>
      {update.isError && (
        <p role="alert" className="w-full text-sm text-red-600">
          {apiErrorMessage(update.error, 'Could not save the details.')}
        </p>
      )}
    </form>
  )
}

type Pending = 'publish' | 'retire' | null

function LifecycleActions({ profile, lineage }: { profile: JobProfile; lineage?: Lineage }) {
  const navigate = useNavigate()
  const [pending, setPending] = useState<Pending>(null)
  const publish = usePublishJobProfile(profile.id)
  const retire = useRetireJobProfile(profile.id)
  const newVersion = useNewProfileVersion(profile.id)

  const openDraft = lineage?.openDraft
  // New versions branch from the current published version, never an older one.
  const latestPublished = lineage?.latestPublished
  const previous = lineage?.versions.find(
    (v) => v.status === 'published' && v.version < profile.version,
  )
  const error = publish.error ?? retire.error ?? newVersion.error

  if (profile.status === 'retired') {
    return (
      <p className={`mt-5 ${CARD} text-sm text-ink-soft`}>
        This version is retired. It isn’t offered as a target; readiness already recorded against it
        is kept.
      </p>
    )
  }

  return (
    <div className="mt-5">
      <div className="flex flex-wrap gap-2">
        {profile.status === 'draft' && (
          <button
            type="button"
            className={PRIMARY_BUTTON}
            style={PRIMARY_STYLE}
            onClick={() => setPending('publish')}
            disabled={pending !== null}
          >
            Publish v{profile.version}
          </button>
        )}
        {profile.status === 'published' &&
          (latestPublished && latestPublished.id !== profile.id ? (
            <Link to={`/career-paths/${latestPublished.id}`} className={SECONDARY_BUTTON}>
              Open current v{latestPublished.version}
            </Link>
          ) : openDraft ? (
            <Link to={`/career-paths/${openDraft.id}`} className={SECONDARY_BUTTON}>
              Continue draft v{openDraft.version}
            </Link>
          ) : (
            <button
              type="button"
              className={PRIMARY_BUTTON}
              style={PRIMARY_STYLE}
              disabled={newVersion.isPending}
              onClick={() =>
                newVersion.mutate(undefined, {
                  onSuccess: (draft) => navigate(`/career-paths/${draft.id}`),
                })
              }
            >
              Edit as new version
            </button>
          ))}
        <button
          type="button"
          className={SECONDARY_BUTTON}
          onClick={() => setPending('retire')}
          disabled={pending !== null}
        >
          Retire
        </button>
      </div>

      {pending === 'publish' && (
        <ConfirmPanel
          title={`Publish v${profile.version} of ${profile.title}?`}
          confirmLabel="Confirm publish"
          busy={publish.isPending}
          onCancel={() => setPending(null)}
          onConfirm={() => publish.mutate(undefined, { onSuccess: () => setPending(null) })}
        >
          Its requirements lock, and it becomes the version learners and managers target.
          {previous &&
            ` Readiness already recorded against v${previous.version} stays pinned to v${previous.version}.`}
        </ConfirmPanel>
      )}
      {pending === 'retire' && (
        <ConfirmPanel
          title={`Retire v${profile.version} of ${profile.title}?`}
          confirmLabel="Confirm retire"
          busy={retire.isPending}
          onCancel={() => setPending(null)}
          onConfirm={() => retire.mutate(undefined, { onSuccess: () => setPending(null) })}
        >
          It stops being offered as a target. This can’t be undone; recorded readiness is kept.
        </ConfirmPanel>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {apiErrorMessage(error, 'That change didn’t go through.')}
        </p>
      )}
    </div>
  )
}

function ConfirmPanel({
  title,
  children,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string
  children: ReactNode
  confirmLabel: string
  busy: boolean
  onConfirm: () => void
  onCancel: () => void
}) {
  return (
    <div role="alertdialog" aria-label={title} className={`mt-3 ${CARD}`}>
      <p className="font-semibold text-ink">{title}</p>
      <p className="mt-1 text-sm text-ink-soft">{children}</p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className={PRIMARY_BUTTON}
          style={PRIMARY_STYLE}
          onClick={onConfirm}
          disabled={busy}
        >
          {confirmLabel}
        </button>
        <button type="button" className={SECONDARY_BUTTON} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  )
}

function VersionHistory({ lineage, currentId }: { lineage: Lineage; currentId: string }) {
  return (
    <div className={`mt-5 ${CARD}`}>
      <h2 className="text-sm font-semibold text-ink">Version history</h2>
      <ol className="mt-2 divide-y divide-brand-100" aria-label="Version history">
        {lineage.versions.map((v) => (
          <li key={v.id} className="flex items-center gap-3 py-2 text-sm">
            <span className="w-10 font-mono text-[12px] text-ink-soft">v{v.version}</span>
            <ProfileStatusBadge status={v.status} />
            <span className="flex-1 text-[12.5px] text-ink-soft">
              updated {new Date(v.updated_at).toLocaleDateString()}
            </span>
            {v.id === currentId ? (
              <span className="text-[12.5px] font-semibold text-ink">Viewing</span>
            ) : (
              <Link
                to={`/career-paths/${v.id}`}
                className="text-[12.5px] text-brand-700 hover:underline"
              >
                Open
              </Link>
            )}
          </li>
        ))}
      </ol>
    </div>
  )
}
