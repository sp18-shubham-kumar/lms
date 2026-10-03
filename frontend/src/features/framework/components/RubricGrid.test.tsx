import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../../lib/api'
import { mockSession, renderAt } from '../../../test/utils'
import { RubricGrid } from './RubricGrid'

const LEVELS = [
  {
    level: 1,
    title: 'Aware',
    indicators: ['Knows SELECT'],
    evidence_kinds: ['quiz'],
    min_verifier_level: null,
    validity_months: null,
  },
]

beforeEach(() => mockSession(['taxonomy.edit']))
afterEach(() => vi.restoreAllMocks())

test('tracks unsaved cells and PUTs the whole grid, omitting blank rows', async () => {
  const put = vi.spyOn(api, 'put').mockImplementation((async (_url: string, body: unknown) => ({
    data: body,
  })) as never)
  renderAt(<RubricGrid skillId="s1" levels={LEVELS} editable />)

  expect(screen.getByText('No changes')).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('L2 Title'), { target: { value: 'Working' } })
  fireEvent.change(screen.getByLabelText('L2 Indicators'), {
    target: { value: 'Writes joins\n\n Uses CTEs ' },
  })
  fireEvent.change(screen.getByLabelText('L2 Evidence kinds'), {
    target: { value: 'project, review' },
  })
  fireEvent.change(screen.getByLabelText('L2 Min verifier level'), { target: { value: '3' } })
  expect(screen.getByText('4 unsaved changes')).toBeInTheDocument()
  expect(screen.getByLabelText('L2 Title')).toHaveClass('bg-amber-50')

  fireEvent.click(screen.getByRole('button', { name: 'Save rubric' }))

  await waitFor(() => expect(screen.getByText('Rubric saved ✓')).toBeInTheDocument())
  expect(put).toHaveBeenCalledWith('/skills/s1/levels/', {
    levels: [
      LEVELS[0],
      {
        level: 2,
        title: 'Working',
        indicators: ['Writes joins', 'Uses CTEs'],
        evidence_kinds: ['project', 'review'],
        min_verifier_level: 3,
        validity_months: null,
      },
    ],
  })
})

test('discard restores the saved rubric', () => {
  renderAt(<RubricGrid skillId="s1" levels={LEVELS} editable />)
  fireEvent.change(screen.getByLabelText('L1 Title'), { target: { value: 'Changed' } })
  fireEvent.click(screen.getByRole('button', { name: 'Discard' }))
  expect(screen.getByLabelText('L1 Title')).toHaveValue('Aware')
  expect(screen.getByText('No changes')).toBeInTheDocument()
})

test('read-only grids show values and the reason, with no inputs', () => {
  renderAt(<RubricGrid skillId="s1" levels={LEVELS} editable={false} readOnlyReason="Locked." />)
  expect(screen.getByText('Knows SELECT')).toBeInTheDocument()
  expect(screen.getByText('Locked.')).toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Save rubric' })).not.toBeInTheDocument()
})
