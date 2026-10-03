import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../../lib/api'
import { apiError, mockSession, renderAt, skill } from '../../../test/utils'
import type { ApiSkill } from '../../skills/types'
import { PrerequisitesEditor } from './PrerequisitesEditor'

const sql = skill() as ApiSkill
const python = skill({ id: 's2', name: 'Python', slug: 'python' }) as ApiSkill

beforeEach(() => {
  mockSession(['taxonomy.edit'])
  vi.spyOn(api, 'get').mockResolvedValue({
    data: { edges: [{ id: 'e1', from_skill: 's1', to_skill: 's2', kind: 'adjacent' }] },
  } as never)
})
afterEach(() => vi.restoreAllMocks())

test('shows the server’s cycle error when adding a link', async () => {
  const post = vi
    .spyOn(api, 'post')
    .mockRejectedValue(apiError(400, 'This prerequisite edge would create a cycle.'))
  renderAt(<PrerequisitesEditor skill={sql} catalogue={[sql, python]} editable />)

  expect(await screen.findByText('Python', { selector: 'span' })).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Linked skill'), { target: { value: 's2' } })
  fireEvent.click(screen.getByRole('button', { name: 'Add link' }))

  expect(await screen.findByRole('alert')).toHaveTextContent(
    'This prerequisite edge would create a cycle.',
  )
  expect(post).toHaveBeenCalledWith('/skills/s1/edges/', { to_skill: 's2', kind: 'prerequisite' })
})

test('removing a link needs a confirm', async () => {
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null } as never)
  renderAt(<PrerequisitesEditor skill={sql} catalogue={[sql, python]} editable />)

  fireEvent.click(await screen.findByRole('button', { name: 'Remove' }))
  expect(del).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Remove' }))
  await waitFor(() =>
    expect(del).toHaveBeenCalledWith('/skills/s1/edges/', { params: { edge: 'e1' } }),
  )
})

test('global skills are read-only', async () => {
  renderAt(<PrerequisitesEditor skill={sql} catalogue={[sql, python]} editable={false} />)
  expect(await screen.findByText('Python', { selector: 'span' })).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Remove' })).not.toBeInTheDocument()
  expect(screen.queryByLabelText('Linked skill')).not.toBeInTheDocument()
})
