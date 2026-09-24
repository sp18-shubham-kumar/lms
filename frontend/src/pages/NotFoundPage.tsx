import { Link } from 'react-router-dom'

export function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
      <h1 className="text-3xl font-semibold text-slate-900">404</h1>
      <p className="text-slate-600">That page doesn&apos;t exist.</p>
      <Link to="/" className="text-sm font-medium" style={{ color: 'var(--tenant-accent)' }}>
        Back to dashboard
      </Link>
    </div>
  )
}
