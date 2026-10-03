/**
 * Public join page for an invite link: /invite/accept?token=...
 *
 * Setting a password consumes the one-time token and opens the membership. The
 * person then signs in normally, with their email prefilled.
 */
import { useState, type FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { AuthCard, authInputClass, authPrimaryButtonClass } from '../components/AuthCard'
import { useAcceptInvitation } from '../features/invitations/api'
import { apiErrorMessage } from '../lib/errors'

export function AcceptInvitePage() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const accept = useAcceptInvitation()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)

  if (!token) {
    return (
      <AuthCard
        title="Invite link incomplete"
        subtitle="This link is missing its token. Open the link from your invite email again, or ask your admin to resend it."
      >
        <Link to="/login" className="text-sm font-semibold text-brand-700 hover:underline">
          Go to sign in
        </Link>
      </AuthCard>
    )
  }

  if (accept.isSuccess) {
    const { email } = accept.data
    return (
      <AuthCard title="You're in" subtitle={`Your password is set. Sign in as ${email}.`}>
        <Link
          to={`/login?email=${encodeURIComponent(email)}`}
          className={`block text-center ${authPrimaryButtonClass}`}
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          Sign in
        </Link>
      </AuthCard>
    )
  }

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError("The passwords don't match.")
      return
    }
    try {
      await accept.mutateAsync({ token, password })
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not accept the invitation.'))
    }
  }

  return (
    <AuthCard title="Join your organization" subtitle="Choose a password to finish setting up.">
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block text-sm">
          <span className="text-ink">Password</span>
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
            className={authInputClass}
          />
        </label>
        <label className="block text-sm">
          <span className="text-ink">Confirm password</span>
          <input
            type="password"
            required
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            autoComplete="new-password"
            className={authInputClass}
          />
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={accept.isPending}
          className={authPrimaryButtonClass}
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {accept.isPending ? 'Joining…' : 'Set password and join'}
        </button>
      </form>
    </AuthCard>
  )
}
