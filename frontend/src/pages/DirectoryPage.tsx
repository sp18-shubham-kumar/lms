import { useState } from 'react'
import { Link } from 'react-router-dom'

import { apiErrorMessage } from '../lib/apiError'
import { useDebounced } from '../lib/useDebounced'
import { DirectoryFilters } from '../features/people/components/DirectoryFilters'
import type { PeopleFilters } from '../features/people/types'
import { usePeople } from '../features/people/usePeople'
import { useSkills } from '../features/skills/api'
import { useOrgUnits } from '../features/team/api'

export function DirectoryPage() {
  const [page, setPage] = useState(1)
  const [filters, setFilters] = useState<PeopleFilters>({})
  const { data, isLoading, isError, error } = usePeople(page, useDebounced(filters))
  const skills = useSkills()
  const orgUnits = useOrgUnits()

  const changeFilters = (next: PeopleFilters) => {
    setFilters(next)
    setPage(1)
  }

  const people = data?.results ?? []
  return (
    <div className="mx-auto max-w-4xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">People directory</h1>
      <p className="mt-1 mb-4 text-sm text-ink-soft">
        Find colleagues by skill, level or team.{' '}
        {data && `${data.count} ${data.count === 1 ? 'person' : 'people'}.`}
      </p>

      <DirectoryFilters
        value={filters}
        onChange={changeFilters}
        skills={skills.data ?? []}
        orgUnits={orgUnits.data ?? []}
      />

      <div className="mt-4">
        {isLoading ? (
          <p className="text-ink-soft">Loading people…</p>
        ) : isError ? (
          <p className="rounded-xl border border-brand-100 bg-white p-6 text-center text-ink-soft">
            Couldn’t load the directory. {apiErrorMessage(error)}
          </p>
        ) : people.length === 0 ? (
          <p className="rounded-xl border border-brand-100 bg-white p-6 text-center text-ink-soft">
            No one matches these filters.
          </p>
        ) : (
          <ul className="divide-y divide-brand-50 overflow-hidden rounded-xl border border-brand-100 bg-white">
            {people.map((p) => (
              <li key={p.id}>
                <Link
                  to={`/people/${p.id}`}
                  className="flex items-center justify-between px-4 py-3 hover:bg-brand-50"
                >
                  <div>
                    <div className="font-medium text-ink">{p.display_name}</div>
                    <div className="text-sm text-ink-soft">{p.email}</div>
                  </div>
                  <span className="text-sm text-ink-soft">{p.org_unit ?? '—'}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="mt-4 flex items-center gap-3">
        <button
          disabled={!data?.previous}
          onClick={() => setPage((n) => Math.max(1, n - 1))}
          className="rounded-md border border-brand-100 px-3 py-1 text-sm text-ink-soft disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-ink-soft">Page {page}</span>
        <button
          disabled={!data?.next}
          onClick={() => setPage((n) => n + 1)}
          className="rounded-md border border-brand-100 px-3 py-1 text-sm text-ink-soft disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
