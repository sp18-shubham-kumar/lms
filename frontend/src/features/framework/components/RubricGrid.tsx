/**
 * Spreadsheet-style rubric editor: one row per level, one column per rubric field.
 *
 * Edits stay local until Save, which replaces the whole grid (PUT levels). Cells
 * that differ from the saved rubric are tinted and counted, so the author sees a
 * live diff before committing. A row left completely blank is not saved.
 */
import { useState } from 'react'

import { apiErrorMessage } from '../../../lib/apiError'
import { LEVEL_LABELS } from '../../skills/types'
import { useReplaceLevels } from '../api'
import { RUBRIC_LEVELS, type SkillLevel } from '../types'

type Field = 'title' | 'indicators' | 'evidence' | 'minVerifier' | 'validity'

type Row = Record<Field, string>

const COLUMNS: { field: Field; label: string; hint: string; multiline?: boolean }[] = [
  { field: 'title', label: 'Title', hint: 'e.g. Working' },
  {
    field: 'indicators',
    label: 'Indicators',
    hint: 'What this level looks like — one per line',
    multiline: true,
  },
  { field: 'evidence', label: 'Evidence kinds', hint: 'Comma-separated, e.g. quiz, project' },
  { field: 'minVerifier', label: 'Min verifier level', hint: '1–5' },
  { field: 'validity', label: 'Valid for (months)', hint: 'blank = no expiry' },
]

const EMPTY_ROW: Row = { title: '', indicators: '', evidence: '', minVerifier: '', validity: '' }

function toRow(level?: SkillLevel): Row {
  if (!level) return EMPTY_ROW
  return {
    title: level.title,
    indicators: level.indicators.join('\n'),
    evidence: level.evidence_kinds.join(', '),
    minVerifier: level.min_verifier_level?.toString() ?? '',
    validity: level.validity_months?.toString() ?? '',
  }
}

function toLevel(level: number, row: Row): SkillLevel {
  const list = (text: string, sep: string) =>
    text
      .split(sep)
      .map((item) => item.trim())
      .filter(Boolean)
  const num = (text: string) => (text.trim() === '' ? null : Number(text))
  return {
    level,
    title: row.title.trim(),
    indicators: list(row.indicators, '\n'),
    evidence_kinds: list(row.evidence, ','),
    min_verifier_level: num(row.minVerifier),
    validity_months: num(row.validity),
  }
}

function toRows(levels: SkillLevel[]): Record<number, Row> {
  const byLevel = new Map(levels.map((l) => [l.level, l]))
  return Object.fromEntries(RUBRIC_LEVELS.map((n) => [n, toRow(byLevel.get(n))]))
}

const isBlank = (row: Row) => Object.values(row).every((value) => value.trim() === '')

function levelLabel(level: number): string {
  return LEVEL_LABELS[level] ?? `L${level}`
}

interface RubricGridProps {
  skillId: string
  levels: SkillLevel[]
  editable: boolean
  /** Shown instead of the editing controls when the grid is read-only. */
  readOnlyReason?: string
}

export function RubricGrid({ skillId, levels, editable, readOnlyReason }: RubricGridProps) {
  // The last saved grid is the diff baseline. Saving resets it to the server's
  // response, so the counter reflects what's actually stored.
  const [saved, setSaved] = useState(() => toRows(levels))
  const [draft, setDraft] = useState(saved)
  const [savedNotice, setSavedNotice] = useState(false)
  const replace = useReplaceLevels(skillId)

  const changedCells = RUBRIC_LEVELS.flatMap((n) =>
    COLUMNS.filter(({ field }) => draft[n][field] !== saved[n][field]).map(
      ({ field }) => `${n}.${field}`,
    ),
  )
  const changed = new Set(changedCells)

  const setCell = (level: number, field: Field, value: string) => {
    setSavedNotice(false)
    setDraft((prev) => ({ ...prev, [level]: { ...prev[level], [field]: value } }))
  }

  const save = () =>
    replace.mutate(
      RUBRIC_LEVELS.filter((n) => !isBlank(draft[n])).map((n) => toLevel(n, draft[n])),
      {
        onSuccess: (result) => {
          const rows = toRows(result)
          setSaved(rows)
          setDraft(rows)
          setSavedNotice(true)
        },
      },
    )

  return (
    <div>
      <div className="overflow-x-auto rounded-xl border border-brand-100 bg-white">
        <table className="w-full border-collapse text-[12.5px]">
          <thead>
            <tr className="border-b border-brand-100 bg-brand-50/60 text-left text-[11px] uppercase tracking-wide text-ink-soft">
              <th className="w-24 px-3 py-2 font-semibold">Level</th>
              {COLUMNS.map((c) => (
                <th key={c.field} className="px-3 py-2 font-semibold">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {RUBRIC_LEVELS.map((n) => (
              <tr key={n} className="border-b border-brand-50 align-top last:border-0">
                <td className="px-3 py-2">
                  <div className="font-semibold text-ink">L{n}</div>
                  <div className="text-[11px] text-ink-soft">{levelLabel(n)}</div>
                </td>
                {COLUMNS.map(({ field, label, hint, multiline }) => {
                  const value = draft[n][field]
                  const cellLabel = `L${n} ${label}`
                  const tint = changed.has(`${n}.${field}`) ? 'bg-amber-50' : ''
                  if (!editable) {
                    return (
                      <td key={field} className="whitespace-pre-line px-3 py-2 text-ink">
                        {value || <span className="text-ink-soft">—</span>}
                      </td>
                    )
                  }
                  const common = {
                    'aria-label': cellLabel,
                    placeholder: hint,
                    value,
                    className: `w-full rounded-md border border-brand-100 px-2 py-1 text-[12.5px] text-ink ${tint}`,
                  }
                  return (
                    <td key={field} className="px-2 py-1.5">
                      {multiline ? (
                        <textarea
                          {...common}
                          rows={3}
                          onChange={(e) => setCell(n, field, e.target.value)}
                        />
                      ) : (
                        <input
                          {...common}
                          inputMode={
                            field === 'minVerifier' || field === 'validity' ? 'numeric' : undefined
                          }
                          onChange={(e) => setCell(n, field, e.target.value)}
                        />
                      )}
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {editable ? (
        <div className="mt-3 flex items-center gap-2">
          <button
            type="button"
            onClick={save}
            disabled={replace.isPending || changedCells.length === 0}
            className="rounded-lg px-3 py-1.5 text-[13px] font-semibold text-white disabled:opacity-50"
            style={{ backgroundColor: 'var(--tenant-accent)' }}
          >
            Save rubric
          </button>
          <button
            type="button"
            onClick={() => setDraft(saved)}
            disabled={replace.isPending || changedCells.length === 0}
            className="rounded-lg border border-brand-200 px-3 py-1.5 text-[13px] font-semibold text-brand-700 hover:bg-brand-50 disabled:opacity-50"
          >
            Discard
          </button>
          <span className="text-[12.5px] text-ink-soft">
            {changedCells.length > 0
              ? `${changedCells.length} unsaved change${changedCells.length === 1 ? '' : 's'}`
              : savedNotice
                ? 'Rubric saved ✓'
                : 'No changes'}
          </span>
          {replace.isError && (
            <span role="alert" className="text-[12.5px] text-red-600">
              {apiErrorMessage(replace.error, 'Could not save the rubric.')}
            </span>
          )}
        </div>
      ) : (
        readOnlyReason && <p className="mt-3 text-[12.5px] text-ink-soft">{readOnlyReason}</p>
      )}
    </div>
  )
}
