/**
 * Career paths (P2-R4): tracks and the job grades on each, for people holding
 * `jobprofile.edit`. Each grade is shown once with its newest version's state;
 * opening it leads to the requirement editor and version history.
 */
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { useAuth } from '../../lib/auth'
import { apiErrorMessage } from '../../lib/errors'
import {
  useAllJobProfiles,
  useCreateJobProfile,
  useCreateTrack,
  useDeleteTrack,
  useRenameTrack,
  useTracks,
} from './api'
import { ProfileStatusBadge } from './components/StatusBadge'
import {
  CARD,
  INPUT,
  LABEL,
  PRIMARY_BUTTON,
  PRIMARY_STYLE,
  SECONDARY_BUTTON,
} from './components/styles'
import { groupLineages, type Lineage } from './lineage'
import { EDIT_CAPABILITY, type Track } from './types'

export function CareerPathsPage() {
  const { hasCapability } = useAuth()
  if (!hasCapability(EDIT_CAPABILITY)) {
    return (
      <section className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-bold tracking-tight text-ink">Career paths</h1>
        <p className={`mt-5 ${CARD} text-sm text-ink-soft`}>
          Editing career paths needs the <span className="font-mono">jobprofile.edit</span>{' '}
          capability. Ask a tenant admin if you should have it.
        </p>
      </section>
    )
  }
  return <CareerPathsEditor />
}

function CareerPathsEditor() {
  const tracks = useTracks()
  const profiles = useAllJobProfiles()

  const lineagesByTrack = new Map<string, Lineage[]>()
  for (const lineage of groupLineages(profiles.data ?? [])) {
    lineagesByTrack.set(lineage.track, [...(lineagesByTrack.get(lineage.track) ?? []), lineage])
  }

  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">Career paths</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Tracks hold job grades; each grade lists the skills and levels it requires. Changes are
        drafted, then published as a new version.
      </p>

      <NewTrackForm />

      {(tracks.isLoading || profiles.isLoading) && (
        <p className="mt-5 text-ink-soft">Loading career paths…</p>
      )}
      {(tracks.isError || profiles.isError) && (
        <p className="mt-5 text-ink-soft">Could not load career paths.</p>
      )}
      {tracks.data?.length === 0 && (
        <p className={`mt-5 ${CARD} text-sm text-ink-soft`}>
          No tracks yet. Create one above, then add its grades.
        </p>
      )}

      <div className="mt-5 space-y-4">
        {(tracks.data ?? []).map((track) => (
          <TrackCard key={track.id} track={track} lineages={lineagesByTrack.get(track.id) ?? []} />
        ))}
      </div>
    </section>
  )
}

function NewTrackForm() {
  const [name, setName] = useState('')
  const create = useCreateTrack()

  const submit = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    create.mutate(name.trim(), { onSuccess: () => setName('') })
  }

  return (
    <form onSubmit={submit} className="mt-5 flex flex-wrap items-center gap-2">
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="New track, e.g. Data Engineering"
        aria-label="New track name"
        className={`${INPUT} w-72`}
      />
      <button
        type="submit"
        disabled={!name.trim() || create.isPending}
        className={PRIMARY_BUTTON}
        style={PRIMARY_STYLE}
      >
        New track
      </button>
      {create.isError && (
        <p role="alert" className="w-full text-sm text-red-600">
          {apiErrorMessage(create.error, 'Could not create the track.')}
        </p>
      )}
    </form>
  )
}

function TrackCard({ track, lineages }: { track: Track; lineages: Lineage[] }) {
  const [renaming, setRenaming] = useState(false)
  const [name, setName] = useState(track.name)
  const [confirmDelete, setConfirmDelete] = useState(false)
  const rename = useRenameTrack()
  const remove = useDeleteTrack()

  const submitRename = (e: FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    rename.mutate({ id: track.id, name: name.trim() }, { onSuccess: () => setRenaming(false) })
  }

  const error = rename.error ?? remove.error

  return (
    <article className={CARD} aria-label={`Track ${track.name}`}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        {renaming ? (
          <form onSubmit={submitRename} className="flex items-center gap-2">
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              aria-label="Track name"
              className={INPUT}
              autoFocus
            />
            <button type="submit" className={PRIMARY_BUTTON} style={PRIMARY_STYLE}>
              Save
            </button>
            <button
              type="button"
              className={SECONDARY_BUTTON}
              onClick={() => {
                setName(track.name)
                setRenaming(false)
              }}
            >
              Cancel
            </button>
          </form>
        ) : (
          <h2 className="text-lg font-semibold text-ink">{track.name}</h2>
        )}
        {!renaming && (
          <div className="flex gap-2">
            <button type="button" className={SECONDARY_BUTTON} onClick={() => setRenaming(true)}>
              Rename
            </button>
            {confirmDelete ? (
              <>
                <button
                  type="button"
                  className={PRIMARY_BUTTON}
                  style={PRIMARY_STYLE}
                  onClick={() => remove.mutate(track.id)}
                  disabled={remove.isPending}
                >
                  Confirm delete
                </button>
                <button
                  type="button"
                  className={SECONDARY_BUTTON}
                  onClick={() => setConfirmDelete(false)}
                >
                  Keep
                </button>
              </>
            ) : (
              <button
                type="button"
                className={SECONDARY_BUTTON}
                onClick={() => setConfirmDelete(true)}
              >
                Delete
              </button>
            )}
          </div>
        )}
      </div>
      {error && (
        <p role="alert" className="mt-2 text-sm text-red-600">
          {apiErrorMessage(error, 'Could not update the track.')}
        </p>
      )}

      {lineages.length === 0 ? (
        <p className="mt-3 text-sm text-ink-soft">No grades on this track yet.</p>
      ) : (
        <ol className="mt-3 divide-y divide-brand-100">
          {lineages.map((l) => (
            <li key={l.key} className="flex items-center gap-3 py-2">
              <span className={`${LABEL} w-14`}>G{l.grade}</span>
              <Link
                to={`/career-paths/${l.latest.id}`}
                className="flex-1 font-medium text-ink hover:underline"
              >
                {l.title}
              </Link>
              <span className="font-mono text-[11px] text-ink-soft">v{l.latest.version}</span>
              <ProfileStatusBadge status={l.latest.status} />
              {l.openDraft && l.latestPublished && (
                <span className="text-[11px] text-ink-soft">v{l.latestPublished.version} live</span>
              )}
            </li>
          ))}
        </ol>
      )}

      <AddGradeForm track={track} nextGrade={Math.max(0, ...lineages.map((l) => l.grade)) + 1} />
    </article>
  )
}

function AddGradeForm({ track, nextGrade }: { track: Track; nextGrade: number }) {
  const navigate = useNavigate()
  const [open, setOpen] = useState(false)
  const [grade, setGrade] = useState(String(nextGrade))
  const [title, setTitle] = useState('')
  const create = useCreateJobProfile()

  if (!open) {
    return (
      <button
        type="button"
        className={`mt-3 ${SECONDARY_BUTTON}`}
        onClick={() => {
          setGrade(String(nextGrade))
          setOpen(true)
        }}
      >
        Add grade
      </button>
    )
  }

  const submit = (e: FormEvent) => {
    e.preventDefault()
    create.mutate(
      { track: track.id, grade: Number(grade), title: title.trim() },
      { onSuccess: (profile) => navigate(`/career-paths/${profile.id}`) },
    )
  }

  return (
    <form onSubmit={submit} className="mt-3 flex flex-wrap items-end gap-2">
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
      <label className={LABEL}>
        Title
        <input
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={`${track.name} L${grade}`}
          className={`${INPUT} ml-2 w-60 font-sans normal-case tracking-normal`}
        />
      </label>
      <button
        type="submit"
        disabled={!title.trim() || !grade || create.isPending}
        className={PRIMARY_BUTTON}
        style={PRIMARY_STYLE}
      >
        Create draft
      </button>
      <button type="button" className={SECONDARY_BUTTON} onClick={() => setOpen(false)}>
        Cancel
      </button>
      {create.isError && (
        <p role="alert" className="w-full text-sm text-red-600">
          {apiErrorMessage(create.error, 'Could not create the grade.')}
        </p>
      )}
    </form>
  )
}
