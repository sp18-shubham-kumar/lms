import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'

import { useAuth } from '../lib/auth'
import { useTenant } from '../lib/tenant'

export function LoginPage() {
  const { login, loadSession, enterDemo } = useAuth()
  const { setTenant } = useTenant()
  const navigate = useNavigate()

  // Dev-only: preview the UI with mock data, no backend required.
  const startDemo = () => {
    setTenant({ id: 'demo-acme', name: 'Acme Data', accentColor: '#0d9488' })
    enterDemo()
    navigate('/')
  }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const memberships = await login(email, password)
      if (memberships.length === 1) {
        const m = memberships[0]
        setTenant({ id: m.tenant_id, name: m.name, accentColor: m.accent_color })
        await loadSession()
        navigate('/')
      } else {
        navigate('/choose', { state: { memberships } })
      }
    } catch {
      setError('Invalid email or password.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center bg-slate-50">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm space-y-4 rounded-xl border border-slate-200 bg-white p-8 shadow-sm"
      >
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Sign in</h1>
          <p className="mt-1 text-sm text-slate-500">Skills LMS</p>
        </div>
        <label className="block text-sm">
          <span className="text-slate-700">Email</span>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="username"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        <label className="block text-sm">
          <span className="text-slate-700">Password</span>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 outline-none focus:border-slate-400"
          />
        </label>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-md py-2 font-medium text-white disabled:opacity-60"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          {busy ? 'Signing in…' : 'Sign in'}
        </button>

        {import.meta.env.DEV && (
          <button
            type="button"
            onClick={startDemo}
            className="w-full rounded-md border border-brand-200 py-2 text-sm font-medium text-brand-700 hover:bg-brand-50"
          >
            Explore the demo (mock data) →
          </button>
        )}
      </form>
    </div>
  )
}
