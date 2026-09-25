import { useState } from 'react'

import { usePeople } from '../features/people/usePeople'

export function DirectoryPage() {
  const [page, setPage] = useState(1)
  const { data, isLoading, isError } = usePeople(page)

  if (isLoading) return <p className="p-6 text-slate-500">Loading people…</p>
  if (isError) return <p className="p-6 text-red-600">Could not load the directory.</p>

  const people = data?.results ?? []
  return (
    <div className="p-6">
      <h1 className="mb-4 text-xl font-semibold text-slate-900">People directory</h1>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {people.map((p) => (
          <li key={p.id} className="flex items-center justify-between px-4 py-3">
            <div>
              <div className="font-medium text-slate-800">{p.display_name}</div>
              <div className="text-sm text-slate-500">{p.email}</div>
            </div>
            <span className="text-sm text-slate-500">{p.org_unit ?? '—'}</span>
          </li>
        ))}
      </ul>
      <div className="mt-4 flex items-center gap-3">
        <button
          disabled={!data?.previous}
          onClick={() => setPage((n) => Math.max(1, n - 1))}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Previous
        </button>
        <span className="text-sm text-slate-500">Page {page}</span>
        <button
          disabled={!data?.next}
          onClick={() => setPage((n) => n + 1)}
          className="rounded-md border border-slate-300 px-3 py-1 text-sm disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
