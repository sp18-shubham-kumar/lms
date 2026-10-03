import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { mockSession, page, renderAt, skill } from '../../test/utils'
import { FrameworkHome } from './FrameworkHome'

beforeEach(() => {
  mockSession(['taxonomy.edit'])
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url.includes('domains')) {
      return page([
        { id: 'd1', tenant: null, name: 'Data', sort: 0 },
        { id: 'd2', tenant: 't1', name: 'Platform', sort: 1 },
      ])
    }
    if (url.includes('overrides')) {
      return page([
        { id: 'o1', skill: 'g9', skill_name: 'COBOL', name: '', status: '', hidden: true },
      ])
    }
    return page([
      skill({ id: 'v1', version: 1, status: 'published' }),
      skill({ id: 'v2', version: 2, status: 'draft' }),
      skill({ id: 'k1', domain: 'd2', name: 'Kubernetes', slug: 'k8s', status: 'published' }),
    ])
  }) as never)
})
afterEach(() => vi.restoreAllMocks())

test('lists the latest version of each skill, grouped by domain', async () => {
  renderAt(<FrameworkHome />)
  const sql = await screen.findByRole('link', { name: /SQL/ })
  expect(sql).toHaveAttribute('href', '/framework/skills/v2')
  expect(screen.getAllByRole('link', { name: /SQL/ })).toHaveLength(1)
  expect(screen.getByRole('heading', { name: 'Platform' })).toBeInTheDocument()
  expect(screen.getByText('2 skills')).toBeInTheDocument()

  fireEvent.change(screen.getByLabelText('Status'), { target: { value: 'published' } })
  expect(screen.queryByRole('link', { name: /SQL/ })).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Kubernetes/ })).toBeInTheDocument()
})

test('only tenant domains can be renamed', async () => {
  renderAt(<FrameworkHome />)
  await screen.findByRole('link', { name: /SQL/ })
  expect(screen.getAllByRole('button', { name: 'Rename' })).toHaveLength(1)
})

test('a hidden global skill can be unhidden', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)
  renderAt(<FrameworkHome />)
  fireEvent.click(await screen.findByRole('button', { name: 'Unhide' }))
  await waitFor(() => expect(post).toHaveBeenCalledWith('/skills/g9/override/', { hidden: false }))
})

test('creating a skill opens its editor', async () => {
  vi.spyOn(api, 'post').mockResolvedValue({ data: skill({ id: 'new1' }) } as never)
  renderAt(<FrameworkHome />)
  fireEvent.click(await screen.findByRole('button', { name: '+ New skill' }))
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Data Modeling' } })
  expect(screen.getByLabelText('Slug')).toHaveValue('data-modeling')
  fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))
  expect(await screen.findByTestId('navigated')).toBeInTheDocument()
})
