/**
 * Platform console (platform operators only): create an organization with its
 * first admin, and list existing organizations.
 *
 * Creating a tenant emails the first admin an accept link. The link is also shown
 * here once, so the operator can hand it over when mail isn't configured.
 */
import { useState, type FormEvent } from 'react'

import { CopyField } from '../../components/CopyField'
import { apiErrorMessage } from '../../lib/errors'
import { usePlatformTenants, useProvisionTenant } from './api'
import { SLUG_MAX, slugify } from './slug'
import type { ProvisionedTenant } from './types'

const inputClass =
  'mt-1 w-full rounded-lg border border-brand-100 px-3 py-1.5 text-[13px] text-ink outline-none focus:border-brand-300'

export function PlatformConsole() {
  const tenants = usePlatformTenants()
  const provision = useProvisionTenant()

  const [name, setName] = useState('')
  const [slug, setSlug] = useState('')
  const [slugEdited, setSlugEdited] = useState(false)
  const [adminEmail, setAdminEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [created, setCreated] = useState<ProvisionedTenant | null>(null)

  const effectiveSlug = slugEdited ? slug : slugify(name)

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      const result = await provision.mutateAsync({
        name,
        slug: effectiveSlug,
        admin_email: adminEmail,
      })
      setCreated(result)
      setName('')
      setSlug('')
      setSlugEdited(false)
      setAdminEmail('')
    } catch (err) {
      setError(apiErrorMessage(err, 'Could not create the organization.'))
    }
  }

  return (
    <section className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Organizations</h1>
        <p className="mt-1 text-sm text-ink-soft">
          Create an organization and invite its first admin. The admin sets a password from the
          invite link and can then invite everyone else.
        </p>
      </div>

      <form onSubmit={onSubmit} className="rounded-xl border border-brand-100 bg-white p-4">
        <h2 className="text-sm font-semibold text-ink">New organization</h2>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <label className="block text-[12.5px]">
            <span className="text-ink-soft">Name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Acme Data"
              className={inputClass}
            />
          </label>
          <label className="block text-[12.5px]">
            <span className="text-ink-soft">Slug</span>
            <input
              required
              value={effectiveSlug}
              onChange={(e) => {
                setSlugEdited(true)
                setSlug(e.target.value)
              }}
              pattern="[a-z0-9_-]+"
              maxLength={SLUG_MAX}
              className={`${inputClass} font-mono`}
            />
          </label>
          <label className="block text-[12.5px] sm:col-span-2">
            <span className="text-ink-soft">First admin's email</span>
            <input
              type="email"
              required
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              placeholder="admin@acme.com"
              className={inputClass}
            />
          </label>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <button
            type="submit"
            disabled={provision.isPending}
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            {provision.isPending ? 'Creating…' : 'Create organization'}
          </button>
          {error && (
            <p role="alert" className="text-[12.5px] text-red-600">
              {error}
            </p>
          )}
        </div>
      </form>

      {created && (
        <div className="space-y-2 rounded-xl border border-brand-200 bg-brand-50 p-4">
          <p className="text-[13px] text-ink">
            <span className="font-semibold">{created.tenant.name}</span> is ready.{' '}
            {created.admin.email} was invited as {created.role}. Send them this link if the email
            doesn't arrive. It is shown only once.
          </p>
          {created.invitation.invite_url && (
            <CopyField label="Admin accept link" value={created.invitation.invite_url} />
          )}
        </div>
      )}

      <div className="rounded-xl border border-brand-100 bg-white p-4">
        <h2 className="text-sm font-semibold text-ink">All organizations</h2>
        {tenants.isLoading ? (
          <p className="mt-2 text-[13px] text-ink-soft">Loading…</p>
        ) : tenants.isError ? (
          <p className="mt-2 text-[13px] text-red-600">
            {apiErrorMessage(tenants.error, 'Could not load organizations.')}
          </p>
        ) : (tenants.data ?? []).length === 0 ? (
          <p className="mt-2 text-[13px] text-ink-soft">No organizations yet.</p>
        ) : (
          <table className="mt-2 w-full text-left text-[13px]">
            <thead className="text-[11px] uppercase tracking-wide text-ink-soft">
              <tr>
                <th className="py-1.5 font-medium">Name</th>
                <th className="py-1.5 font-medium">Slug</th>
                <th className="py-1.5 text-right font-medium">Members</th>
                <th className="py-1.5 text-right font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {(tenants.data ?? []).map((t) => (
                <tr key={t.id} className="border-t border-brand-50">
                  <td className="py-2">
                    <span className="inline-flex items-center gap-2 text-ink">
                      <span
                        className="inline-block h-3 w-3 rounded-sm"
                        style={{ backgroundColor: t.accent_color || 'var(--tenant-accent)' }}
                      />
                      {t.name}
                    </span>
                  </td>
                  <td className="py-2 font-mono text-[12px] text-ink-soft">{t.slug}</td>
                  <td className="py-2 text-right font-mono text-[12px] text-ink">
                    {t.member_count}
                  </td>
                  <td className="py-2 text-right text-ink-soft">{t.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
