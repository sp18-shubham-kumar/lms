import { useState, type FormEvent } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { AuthCard, authInputClass, authPrimaryButtonClass } from '../components/AuthCard'
import { useAuth } from '../lib/auth'
import { apiErrorMessage, apiErrorStatus } from '../lib/errors'
import { useTenant } from '../lib/tenant'
import { useEnterTenant } from '../lib/useEnterTenant'

const NO_MEMBERSHIP_MESSAGE =
  "Your account isn't part of any organization yet. Ask your organization's admin to " +
  'invite you, then open the link in the invite email.'

function loginErrorMessage(error: unknown): string {
  const status = apiErrorStatus(error)
  if (status === 401) return 'Invalid email or password.'
  if (status === 403) return NO_MEMBERSHIP_MESSAGE
  return apiErrorMessage(error, 'Sign-in failed. Please try again.')
}

export function LoginPage() {
  const { login, enterDemo } = useAuth()
  const { setTenant } = useTenant()
  const enterTenant = useEnterTenant()
  const navigate = useNavigate()
  const [params] = useSearchParams()

  // Dev-only: preview the UI with mock data, no backend required.
  const startDemo = () => {
    setTenant({ id: 'demo-acme', name: 'Acme Data', accentColor: '#0d9488' })
    enterDemo()
    navigate('/')
  }
  // Prefilled after accepting an invitation.
  const [email, setEmail] = useState(params.get('email') ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const { memberships, isPlatformOperator } = await login(email, password)
      if (memberships.length === 1 && !isPlatformOperator) {
        await enterTenant(memberships[0])
        navigate('/')
        return
      }
      // Don't carry a previous person's tenant into the next screen.
      setTenant(null)
      // Only platform operators get past login with no memberships.
      navigate(memberships.length === 0 ? '/platform' : '/choose')
    } catch (err) {
      setError(loginErrorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthCard title="Sign in">
      <form onSubmit={onSubmit} className="space-y-4">
        <label className="block text-sm">
          <span className="text-ink">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            className={authInputClass}
          />
        </label>
        <label className="block text-sm">
          <span className="text-ink">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
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
          disabled={busy}
          className={authPrimaryButtonClass}
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        {import.meta.env.DEV && (
          <button
            type="button"
            onClick={startDemo}
            className="w-full rounded-lg border border-brand-200 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
          >
            Explore the demo (mock data) →
          </button>
        )}
      </form>
    </AuthCard>
  )
}
