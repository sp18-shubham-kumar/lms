/**
 * Import tab: CSV member import.
 *
 * Two-step, pessimistic flow — Preview runs a dry-run diff, Apply commits it —
 * matching the "explicit confirm for state-changing actions" rule.
 */
import { useState } from 'react'

import { apiErrorMessage } from '../../../lib/errors'
import { useImportMembers } from '../api'
import type { ImportDiff } from '../types'

const SAMPLE_CSV = `email,display_name,org_unit_path,role,employee_ref
newbie@acme.test,New Bie,,Learner,E100`

export function ImportPanel() {
  const importer = useImportMembers()

  const [csv, setCsv] = useState(SAMPLE_CSV)
  const [preview, setPreview] = useState<ImportDiff | null>(null)
  const [committed, setCommitted] = useState(false)

  // mutate (not mutateAsync): a failure is shown via importer.isError, not thrown.
  const runPreview = () => {
    setCommitted(false)
    importer.mutate({ csv, commit: false }, { onSuccess: setPreview })
  }
  const runApply = () => {
    importer.mutate(
      { csv, commit: true },
      {
        onSuccess: (diff) => {
          setPreview(diff)
          setCommitted(true)
        },
      },
    )
  }

  return (
    <div>
      <p className=" text-[12.5px] text-ink-soft">
        Columns: <code>email, display_name, org_unit_path, role, employee_ref</code>. Preview is a
        dry run; Apply commits.
      </p>
      <textarea
        value={csv}
        onChange={(e) => setCsv(e.target.value)}
        rows={5}
        className="mt-2 w-full rounded-lg border border-brand-100 bg-white p-3 font-mono text-[12px] text-ink"
        spellCheck={false}
      />
      <div className="mt-2 flex items-center gap-2">
        <button
          onClick={runPreview}
          disabled={importer.isPending}
          className="rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
        >
          Preview
        </button>
        <button
          onClick={runApply}
          disabled={importer.isPending || !preview}
          className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
          style={{ backgroundColor: 'var(--tenant-accent)' }}
        >
          Apply
        </button>
        {importer.isError && (
          <span className="text-[12.5px] text-red-600">
            Import failed. {apiErrorMessage(importer.error)}
          </span>
        )}
      </div>

      {preview && (
        <div className="mt-3 rounded-xl border border-brand-100 bg-white p-4 text-[13px]">
          <div className="flex gap-4 font-mono text-[12px] text-ink-soft">
            <span>
              <span className="font-semibold text-ink">{preview.adds.length}</span> add
            </span>
            <span>
              <span className="font-semibold text-ink">{preview.updates.length}</span> update
            </span>
            <span>
              <span className="font-semibold text-ink">{preview.errors.length}</span> error
            </span>
            {committed && <span className="font-semibold text-brand-700">· applied ✓</span>}
          </div>
          <ul className="mt-2 space-y-1">
            {preview.adds.map((r) => (
              <li key={`a${r.row}`} className="text-ink-soft">
                <span className="font-mono text-brand-700">+ add</span> {r.email} ({r.role})
              </li>
            ))}
            {preview.updates.map((r) => (
              <li key={`u${r.row}`} className="text-ink-soft">
                <span className="font-mono text-ink">~ update</span> {r.email} ({r.role})
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
