/**
 * Invite members by email and manage pending invitations (gated by member.invite).
 *
 * The accept link is shown right after create/resend because it is only returned
 * once; it is also emailed (in dev, printed in the backend log). Cancel asks for
 * an explicit confirm.
 */
import { useState, type FormEvent } from 'react'

import { CopyField } from '../../components/CopyField'
import { apiErrorMessage } from '../../lib/errors'
import { useRoles } from '../admin/api'
import {
  useCancelInvitation,
  useCreateInvitation,
  usePendingInvitations,
  useResendInvitation,
} from './api'
import type { Invitation } from './types'

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
}

export function InvitationsPanel() {
  const roles = useRoles()
  const pending = usePendingInvitations()
  const create = useCreateInvitation()
  const resend = useResendInvitation()
  const cancel = useCancelInvitation()

  const [email, setEmail] = useState('')
  const [role, setRole] = useState('')
  const [issued, setIssued] = useState<Invitation | null>(null)
  const [confirmingCancel, setConfirmingCancel] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const roleOptions = roles.data ?? []
  const selectedRole = role || roleOptions[0]?.name || ''

  const run = async (action: () => Promise<Invitation | void>, fallback: string) => {
    setError(null)
    try {
      const result = await action()
      setIssued(result ?? null)
    } catch (err) {
      setError(apiErrorMessage(err, fallback))
    }
  }

  const onInvite = (e: FormEvent) => {
    e.preventDefault()
    void run(async () => {
      const invitation = await create.mutateAsync({ email, role: selectedRole })
      setEmail('')
      return invitation
    }, 'Could not send the invitation.')
  }

  const onCancel = (id: string) => {
    setConfirmingCancel(null)
    void run(() => cancel.mutateAsync(id), 'Could not cancel the invitation.')
  }

  const busy = create.isPending || resend.isPending || cancel.isPending

  return (
    <div className="space-y-4">
      <form onSubmit={onInvite} className="rounded-xl border border-brand-100 bg-white p-4">
        <h2 className="text-sm font-semibold text-ink">Invite a member</h2>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <label className="block min-w-60 flex-1 text-[12.5px]">
            <span className="text-ink-soft">Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full rounded-lg border border-brand-100 px-3 py-1.5 text-[13px] text-ink outline-none focus:border-brand-300"
            />
          </label>
          <label className="block text-[12.5px]">
            <span className="text-ink-soft">Role</span>
            <select
              value={selectedRole}
              onChange={(e) => setRole(e.target.value)}
              className="mt-1 block rounded-lg border border-brand-100 bg-white px-3 py-1.5 text-[13px] text-ink"
            >
              {roleOptions.map((r) => (
                <option key={r.id} value={r.name}>
                  {r.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="submit"
            disabled={busy || !selectedRole}
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            Send invite
          </button>
        </div>
      </form>

      {error && (
        <p role="alert" className="text-[12.5px] text-red-600">
          {error}
        </p>
      )}

      {issued?.invite_url && (
        <div className="space-y-2 rounded-xl border border-brand-200 bg-brand-50 p-4">
          <p className="text-[13px] text-ink">
            Invitation sent to <span className="font-semibold">{issued.email}</span> as{' '}
            {issued.role}. Share this link if the email doesn't arrive. It is shown only once.
          </p>
          <CopyField label="Accept link" value={issued.invite_url} />
        </div>
      )}

      <div className="rounded-xl border border-brand-100 bg-white p-4">
        <h2 className="text-sm font-semibold text-ink">Pending invitations</h2>
        {pending.isLoading ? (
          <p className="mt-2 text-[13px] text-ink-soft">Loading…</p>
        ) : pending.isError ? (
          <p className="mt-2 text-[13px] text-red-600">
            {apiErrorMessage(pending.error, 'Could not load invitations.')}
          </p>
        ) : (pending.data ?? []).length === 0 ? (
          <p className="mt-2 text-[13px] text-ink-soft">No pending invitations.</p>
        ) : (
          <table className="mt-2 w-full text-left text-[13px]">
            <thead className="text-[11px] uppercase tracking-wide text-ink-soft">
              <tr>
                <th className="py-1.5 font-medium">Email</th>
                <th className="py-1.5 font-medium">Role</th>
                <th className="py-1.5 font-medium">Expires</th>
                <th className="py-1.5" />
              </tr>
            </thead>
            <tbody>
              {(pending.data ?? []).map((inv) => (
                <tr key={inv.id} className="border-t border-brand-50">
                  <td className="py-2 text-ink">{inv.email}</td>
                  <td className="py-2 text-ink-soft">{inv.role}</td>
                  <td className="py-2 font-mono text-[12px] text-ink-soft">
                    {formatDate(inv.expires_at)}
                  </td>
                  <td className="py-2 text-right">
                    {confirmingCancel === inv.id ? (
                      <span className="inline-flex items-center gap-2 text-[12.5px]">
                        <span className="text-ink-soft">Cancel this invite?</span>
                        <button
                          onClick={() => onCancel(inv.id)}
                          disabled={busy}
                          className="font-semibold text-red-600 hover:underline"
                        >
                          Yes, cancel
                        </button>
                        <button
                          onClick={() => setConfirmingCancel(null)}
                          className="text-ink-soft hover:underline"
                        >
                          Keep
                        </button>
                      </span>
                    ) : (
                      <span className="inline-flex gap-2">
                        <button
                          onClick={() =>
                            void run(
                              () => resend.mutateAsync(inv.id),
                              'Could not resend the invitation.',
                            )
                          }
                          disabled={busy}
                          className="rounded-lg border border-brand-200 px-2.5 py-1 text-[12.5px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
                        >
                          Resend
                        </button>
                        <button
                          onClick={() => setConfirmingCancel(inv.id)}
                          disabled={busy}
                          className="rounded-lg border border-brand-100 px-2.5 py-1 text-[12.5px] text-ink-soft hover:bg-brand-50 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
