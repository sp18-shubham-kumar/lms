/**
 * Members × core-requirements heatmap (GET /profiles/heatmap/).
 *
 * Needs an org_unit and a job_profile; both are chosen from dropdowns fed by the
 * org-units and job-profiles endpoints. Cells show ✓ / · so status never rides
 * on colour alone. Each member links to their gap view for the chosen target;
 * "One gap from promotion" narrows to members missing exactly one requirement.
 */
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { useJobProfiles } from '../roadmap/api'
import { useHeatmap, useOrgUnits } from './api'
import { memberReadinessPath } from './memberLink'
import type { HeatmapRow } from './types'

const unmetCount = (row: HeatmapRow) => row.cells.filter((c) => !c.met).length

export function TeamHeatmap() {
  const orgUnits = useOrgUnits()
  const profiles = useJobProfiles(true)
  const [orgUnitSel, setOrgUnitSel] = useState<string | null>(null)
  const [jobProfileSel, setJobProfileSel] = useState<string | null>(null)
  const [oneGapOnly, setOneGapOnly] = useState(false)

  // Effective selection: explicit choice, else default to the first loaded.
  const orgUnit = orgUnitSel ?? orgUnits.data?.[0]?.id ?? null
  const jobProfile = jobProfileSel ?? profiles.data?.[0]?.id ?? null

  const heatmap = useHeatmap(orgUnit, jobProfile)
  const rows = (heatmap.data?.rows ?? []).filter((r) => !oneGapOnly || unmetCount(r) === 1)

  return (
    <div className="mt-8">
      <h2 className="text-sm font-semibold text-ink">Skill heatmap</h2>

      <div className="mt-2 flex flex-wrap gap-3">
        <select
          value={orgUnit ?? ''}
          onChange={(e) => setOrgUnitSel(e.target.value || null)}
          className="rounded-md border border-brand-100 bg-white px-2 py-1 text-sm text-ink"
          aria-label="Org unit"
        >
          {(orgUnits.data ?? []).map((u) => (
            <option key={u.id} value={u.id}>
              {u.name}
            </option>
          ))}
        </select>
        <select
          value={jobProfile ?? ''}
          onChange={(e) => setJobProfileSel(e.target.value || null)}
          className="rounded-md border border-brand-100 bg-white px-2 py-1 text-sm text-ink"
          aria-label="Target job profile"
        >
          {(profiles.data ?? []).map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </select>
        <label className="flex items-center gap-1.5 text-sm text-ink">
          <input
            type="checkbox"
            checked={oneGapOnly}
            onChange={(e) => setOneGapOnly(e.target.checked)}
          />
          One gap from promotion
        </label>
      </div>

      {(orgUnits.isError || profiles.isError) && (
        <p className="mt-3 text-ink-soft">Couldn’t load org units or job profiles.</p>
      )}
      {!orgUnits.isLoading && !orgUnits.data?.length && (
        <p className="mt-3 text-ink-soft">No org units defined yet — add one to see the heatmap.</p>
      )}
      {heatmap.isLoading && <p className="mt-3 text-ink-soft">Loading heatmap…</p>}
      {heatmap.isError && <p className="mt-3 text-ink-soft">Could not load the heatmap.</p>}
      {heatmap.data && rows.length > 0 ? (
        <div className="mt-3 overflow-x-auto">
          <table className="border-separate border-spacing-1 text-[12px]">
            <thead>
              <tr className="text-ink-soft">
                <th className="px-2 py-1 text-left font-medium"></th>
                {heatmap.data.columns.map((c) => (
                  <th key={c.skill_id} className="px-2 py-1 font-medium">
                    {c.skill_name}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.membership_id}>
                  <td className="whitespace-nowrap px-2 py-1 font-medium text-ink">
                    <Link
                      to={memberReadinessPath(row.membership_id, jobProfile)}
                      className="hover:underline"
                    >
                      {row.display_name}
                    </Link>
                  </td>
                  {row.cells.map((cell, i) => (
                    <td
                      key={i}
                      className="h-7 w-16 rounded text-center font-mono text-[11px]"
                      style={{
                        backgroundColor: cell.met
                          ? 'var(--tenant-accent)'
                          : 'color-mix(in srgb, var(--tenant-accent) 10%, white)',
                        color: cell.met ? '#fff' : 'var(--color-ink-soft)',
                      }}
                    >
                      {cell.met ? '✓' : '·'}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        heatmap.data && (
          <p className="mt-3 text-ink-soft">
            {oneGapOnly && heatmap.data.rows.length > 0
              ? 'Nobody here is exactly one requirement away.'
              : 'No members in this org unit yet.'}
          </p>
        )
      )}
    </div>
  )
}
