import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { mockSession, page, renderAt, skill } from '../../test/utils'
import { SkillEditor } from './SkillEditor'

function serve(current: Record<string, unknown>) {
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.endsWith('/levels/')) return { data: { levels: [] } }
    if (url.endsWith('/edges/')) return { data: { edges: [] } }
    if (url.endsWith('/versions/')) return { data: { versions: [current] } }
    if (url.includes('domains')) return page([{ id: 'd1', tenant: null, name: 'Data', sort: 0 }])
    if (url.includes('overrides')) return page([])
    if (url === '/skills/') return page([current])
    return { data: current }
  }) as never)
}

const open = () =>
  renderAt(<SkillEditor />, { path: '/framework/skills/s1', route: '/framework/skills/:id' })

beforeEach(() => mockSession(['taxonomy.edit']))
afterEach(() => vi.restoreAllMocks())

test('a published tenant skill is locked and offers a new version', async () => {
  serve(skill({ status: 'published' }))
  const post = vi.spyOn(api, 'post').mockResolvedValue({
    data: skill({ id: 's2', version: 2 }),
  } as never)
  open()

  expect(await screen.findByText(/Published versions are locked/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Publish' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start new version' }))
  fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))

  await waitFor(() => expect(post).toHaveBeenCalledWith('/skills/s1/new-version/'))
  // The editor moves to the new draft.
  await waitFor(() => expect(api.get).toHaveBeenCalledWith('/skills/s2/'))
})

test('a draft publishes only after confirming', async () => {
  serve(skill())
  const post = vi
    .spyOn(api, 'post')
    .mockResolvedValue({ data: skill({ status: 'published' }) } as never)
  open()

  fireEvent.click(await screen.findByRole('button', { name: 'Publish' }))
  expect(post).not.toHaveBeenCalled()
  expect(screen.getByRole('group', { name: 'Confirm Publish' })).toHaveTextContent(
    'Publish v1? It becomes read-only.',
  )
  fireEvent.click(screen.getByRole('button', { name: 'Publish' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/skills/s1/publish/'))
})

test('a global skill has no lifecycle actions but can be customized', async () => {
  serve(skill({ tenant: null, status: 'published' }))
  open()

  expect(await screen.findByText(/maintained by the platform/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Retire' })).not.toBeInTheDocument()
  fireEvent.click(screen.getByRole('tab', { name: 'Customize' }))
  expect(
    await screen.findByRole('button', { name: 'Hide for my organization' }),
  ).toBeInTheDocument()
})
