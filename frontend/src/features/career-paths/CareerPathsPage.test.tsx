import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { CareerPathsPage } from './CareerPathsPage'
import { jobProfile, mockSession, page, renderAt } from './testUtils'

beforeEach(() => {
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url === '/profiles/tracks/') return page([{ id: 'tr1', name: 'Data Engineering' }])
    return page([
      jobProfile({ id: 'l1', grade: 1, title: 'Data Engineer L1' }),
      jobProfile({ id: 'l2v1', version: 1 }),
      jobProfile({ id: 'l2v2', version: 2, status: 'draft' }),
    ])
  }) as never)
})

afterEach(() => vi.restoreAllMocks())

const routes = [
  { path: '/career-paths', element: <CareerPathsPage /> },
  { path: '/career-paths/:id', element: <p>detail page</p> },
]

test('each grade appears once, at its newest version, in grade order', async () => {
  mockSession(['jobprofile.edit'])
  render(renderAt('/career-paths', routes))
  const track = await screen.findByRole('article', { name: 'Track Data Engineering' })
  const grades = await within(track).findAllByRole('listitem')
  expect(grades.map((g) => g.textContent)).toEqual([
    expect.stringContaining('Data Engineer L1'),
    expect.stringContaining('Data Engineer L2'),
  ])
  expect(grades[1]).toHaveTextContent(/v2.*draft.*v1 live/)
  expect(within(grades[1]).getByRole('link')).toHaveAttribute('href', '/career-paths/l2v2')
})

test('adding a grade creates a draft on the track and opens it', async () => {
  mockSession(['jobprofile.edit'])
  const post = vi
    .spyOn(api, 'post')
    .mockResolvedValue({ data: jobProfile({ id: 'new', grade: 3, status: 'draft' }) } as never)
  render(renderAt('/career-paths', routes))

  fireEvent.click(await screen.findByRole('button', { name: 'Add grade' }))
  expect(screen.getByRole('spinbutton')).toHaveValue(3)
  fireEvent.change(screen.getByPlaceholderText('Data Engineering L3'), {
    target: { value: 'Data Engineer L3' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))

  expect(await screen.findByText('detail page')).toBeInTheDocument()
  expect(post).toHaveBeenCalledWith('/profiles/job-profiles/', {
    track: 'tr1',
    grade: 3,
    title: 'Data Engineer L3',
  })
})

test('deleting a track asks first and surfaces a 409', async () => {
  mockSession(['jobprofile.edit'])
  const { AxiosError } = await import('axios')
  const del = vi.spyOn(api, 'delete').mockRejectedValue(
    new AxiosError('409', 'ERR', undefined, undefined, {
      status: 409,
      data: { error: { code: 'track_in_use', detail: 'This track still has job profiles.' } },
    } as never),
  )
  render(renderAt('/career-paths', routes))

  fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
  expect(del).not.toHaveBeenCalled()
  fireEvent.click(screen.getByRole('button', { name: 'Confirm delete' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('This track still has job profiles.')
  expect(del).toHaveBeenCalledWith('/profiles/tracks/tr1/')
})

test('without jobprofile.edit there is no editor', () => {
  mockSession(['directory.view'])
  render(renderAt('/career-paths', routes))
  expect(screen.getByText(/needs the/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'New track' })).not.toBeInTheDocument()
})
