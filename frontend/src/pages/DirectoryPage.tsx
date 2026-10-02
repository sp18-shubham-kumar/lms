import { useState } from 'react'

import { usePeople } from '../features/people/usePeople'

export function DirectoryPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = usePeople(page)

  if (isLoading) return <p className="p-6 text-ink-soft">Loading people…</p>
  if (isError)
    return (
      <p className="mx-auto max-w-md rounded-lg border border-brand-100 bg-white p-6 text-center text-ink-soft">
        The directory loads from the backend, which isn’t wired up in this preview.
      </p>
    )

  const people = data?.results ?? []
  return (
    <div>
      <h1 className="mb-4 text-2xl font-bold tracking-tight text-ink">People directory</h1>
      <ul className="divide-y divide-brand-50 overflow-hidden rounded-xl border border-brand-100 bg-white">
        {people.map((p) => (
          <li key={p.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium text-ink">{p.display_name}</div>
              <div className="text-sm text-ink-soft">{p.email}</div>
            </div>
            <span className="text-sm text-ink-soft">{p.org_unit ?? '—'}</span>
          </li>
        ))}
      </ul>
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
