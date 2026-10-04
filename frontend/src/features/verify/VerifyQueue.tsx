/**
 * Verifier queue: members' self-declared skill claims awaiting review.
 *
 * Verifying records a skill assertion (the only readiness input), possibly at a
 * different level than claimed; rejecting needs a reason the member will see.
 * Both open an explicit confirm panel and wait for the server before the row
 * leaves the queue. The server's reason is shown if it refuses (e.g. a verifier
 * reviewing their own claim).
 */
import { useState } from 'react'

import { apiErrorMessage } from '../../lib/errors'
import { LEVEL_LABELS } from '../skills/types'
import { useClaims, useRejectClaim, useVerifyClaim, type ClaimStatus, type SkillClaim } from './api'

const TABS: { key: ClaimStatus; label: string }[] = [
  { key: 'pending', label: 'Pending' },
  { key: 'verified', label: 'Verified' },
  { key: 'rejected', label: 'Rejected' },
  { key: 'all', label: 'All' },
]

const VERIFY_LEVELS = [1, 2, 3, 4, 5]

const levelLabel = (level: number) =>
  `L${level}${LEVEL_LABELS[level] ? ` · ${LEVEL_LABELS[level]}` : ''}`

const INPUT = 'rounded-md border border-brand-100 bg-white px-2.5 py-1.5 text-[13px] text-ink'

export function VerifyQueue() {
  const [status, setStatus] = useState<ClaimStatus>('pending')
  const claims = useClaims(status)

  return (
    <section className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">Verify skills</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Review skills people have claimed. A verification counts toward their readiness.
      </p>

      <div role="tablist" className="mt-5 flex gap-1 border-b border-brand-100">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            aria-selected={status === t.key}
            onClick={() => setStatus(t.key)}
            className={`-mb-px border-b-2 px-3 py-2 text-[13px] font-semibold ${
              status === t.key ? 'text-ink' : 'border-transparent text-ink-soft hover:text-ink'
            }`}
            style={status === t.key ? { borderColor: 'var(--tenant-accent)' } : undefined}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {claims.isLoading ? (
          <p className="text-ink-soft">Loading claims…</p>
        ) : claims.isError ? (
          <p className="text-red-600">{apiErrorMessage(claims.error, 'Couldn’t load claims.')}</p>
        ) : (claims.data ?? []).length === 0 ? (
          <p className="text-ink-soft">
            {status === 'pending' ? 'Nothing waiting for review.' : 'No claims here.'}
          </p>
        ) : (
          <ul className="space-y-2">
            {(claims.data ?? []).map((claim) => (
              <ClaimRow key={claim.id} claim={claim} />
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}

function ClaimRow({ claim }: { claim: SkillClaim }) {
  const verify = useVerifyClaim()
  const reject = useRejectClaim()
  const [mode, setMode] = useState<'idle' | 'verify' | 'reject'>('idle')
  const [level, setLevel] = useState(claim.level)
  const [note, setNote] = useState('')
  const busy = verify.isPending || reject.isPending
  const error = verify.error ?? reject.error
  const pending = claim.review_status === 'pending'

  const open = (next: 'verify' | 'reject') => {
    verify.reset()
    reject.reset()
    setNote('')
    setLevel(claim.level)
    setMode(next)
  }

  return (
    <li className="rounded-xl border border-brand-100 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="text-[13.5px] font-semibold text-ink">
            {claim.person_name || claim.person_email}{' '}
            <span className="font-normal text-ink-soft">claims</span> {claim.skill_name}
          </div>
          <div className="mt-0.5 text-[12.5px] text-ink-soft">
            {levelLabel(claim.level)}
            {claim.person_name && claim.person_email ? ` · ${claim.person_email}` : ''}
          </div>
          {claim.note && <p className="mt-1.5 text-[13px] text-ink">“{claim.note}”</p>}
          {!pending && (
            <p className="mt-1.5 text-[12.5px] text-ink-soft">
              <span className="font-semibold capitalize">{claim.review_status}</span>
              {claim.review_note ? ` — ${claim.review_note}` : ''}
            </p>
          )}
        </div>
        {pending && mode === 'idle' && (
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => open('verify')}
              className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white"
              style={{ backgroundColor: 'var(--tenant-accent)' }}
            >
              Verify
            </button>
            <button
              type="button"
              onClick={() => open('reject')}
              className="rounded-lg border border-red-200 px-3 py-1.5 text-[13px] font-semibold text-red-700 hover:bg-red-50"
            >
              Reject
            </button>
          </div>
        )}
      </div>

      {mode !== 'idle' && (
        <form
          aria-label={mode === 'verify' ? 'Confirm verification' : 'Confirm rejection'}
          className="mt-3 flex flex-wrap items-end gap-2 border-t border-brand-50 pt-3"
          onSubmit={(e) => {
            e.preventDefault()
            if (mode === 'verify') {
              verify.mutate({ id: claim.id, level, note: note.trim() })
            } else if (note.trim()) {
              reject.mutate({ id: claim.id, note: note.trim() })
            }
          }}
        >
          {mode === 'verify' && (
            <label className="text-[12px] font-semibold text-ink-soft">
              Verified level
              <select
                value={level}
                onChange={(e) => setLevel(Number(e.target.value))}
                className={`mt-1 block ${INPUT}`}
              >
                {VERIFY_LEVELS.map((n) => (
                  <option key={n} value={n}>
                    {levelLabel(n)}
                    {n === claim.level ? ' (claimed)' : ''}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className="flex-1 text-[12px] font-semibold text-ink-soft">
            {mode === 'verify' ? 'Note (optional)' : 'Reason (shown to the member)'}
            <input
              value={note}
              required={mode === 'reject'}
              onChange={(e) => setNote(e.target.value)}
              className={`mt-1 block w-full ${INPUT}`}
            />
          </label>
          <button
            type="submit"
            disabled={busy || (mode === 'reject' && !note.trim())}
            className={
              mode === 'verify'
                ? 'rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50'
                : 'rounded-lg bg-red-600 px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50'
            }
            style={mode === 'verify' ? { backgroundColor: 'var(--tenant-accent)' } : undefined}
          >
            {busy ? 'Saving…' : mode === 'verify' ? `Confirm L${level}` : 'Confirm rejection'}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => setMode('idle')}
            className="rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50"
          >
            Cancel
          </button>
          {error != null && (
            <p role="alert" className="w-full text-[12.5px] text-red-600">
              {apiErrorMessage(error, 'Could not record the review.')}
            </p>
          )}
        </form>
      )}
    </li>
  )
}
