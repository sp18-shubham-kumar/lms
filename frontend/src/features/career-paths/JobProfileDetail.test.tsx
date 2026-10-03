import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { JobProfileDetail } from './JobProfileDetail'
import { jobProfile, mockSession, page, renderAt } from './testUtils'

const v1 = jobProfile({ id: 'v1', version: 1, status: 'published' })
const v2 = jobProfile({ id: 'v2', version: 2, status: 'draft' })

const requirements = [
  {
    id: 'r1',
    job_profile: 'v1',
    skill: 's-sql',
    skill_name: 'SQL',
    min_level: 3,
    criticality: 'core',
  },
]

let profiles = [v1]

beforeEach(() => {
  profiles = [v1]
  vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url === '/profiles/tracks/') return page([{ id: 'tr1', name: 'Data Engineering' }])
    if (url === '/profiles/job-profiles/') return page(profiles)
    if (url.endsWith('/requirements/')) return { data: requirements }
    if (url === '/skills/')
      return page([
        { id: 's-sql', name: 'SQL', status: 'published' },
        { id: 's-py', name: 'Python', status: 'published' },
        { id: 's-old', name: 'Perl', status: 'retired' },
      ])
    if (url === '/skills/s-py/levels/')
      return { data: { levels: [{ id: 'l3', level: 3, title: 'Ships pipelines' }] } }
    const id = url.split('/')[3]
    return { data: profiles.find((p) => p.id === id) }
  }) as never)
})

afterEach(() => vi.restoreAllMocks())

const routes = [
  { path: '/career-paths/:id', element: <JobProfileDetail /> },
  { path: '/career-paths', element: <p>career paths list</p> },
]

test('a published version is read-only and offers a new version instead', async () => {
  mockSession(['jobprofile.edit', 'directory.view'])
  render(renderAt('/career-paths/v1', routes))

  expect(await screen.findByText('SQL')).toBeInTheDocument()
  expect(screen.getByText(/This version is locked/)).toBeInTheDocument()
  expect(screen.queryByRole('button', { name: /Remove/ })).not.toBeInTheDocument()
  expect(screen.queryByRole('button', { name: 'Add requirement' })).not.toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Edit as new version' })).toBeInTheDocument()
})

test('"Edit as new version" opens the new draft', async () => {
  mockSession(['jobprofile.edit', 'directory.view'])
  const post = vi.spyOn(api, 'post').mockImplementation((async (url: string) => {
    profiles = [v1, v2]
    expect(url).toBe('/profiles/job-profiles/v1/new-version/')
    return { data: v2 }
  }) as never)
  render(renderAt('/career-paths/v1', routes))

  fireEvent.click(await screen.findByRole('button', { name: 'Edit as new version' }))
  expect(await screen.findByRole('button', { name: 'Publish v2' })).toBeInTheDocument()
  expect(post).toHaveBeenCalledTimes(1)
})

test('a published version with an open draft links to it rather than opening another', async () => {
  profiles = [v1, v2]
  mockSession(['jobprofile.edit', 'directory.view'])
  render(renderAt('/career-paths/v1', routes))
  expect(await screen.findByRole('link', { name: 'Continue draft v2' })).toHaveAttribute(
    'href',
    '/career-paths/v2',
  )
  const history = screen.getByRole('list', { name: 'Version history' })
  expect(within(history).getAllByRole('listitem')).toHaveLength(2)
})

test('a draft is editable: add skill picker excludes taken and retired skills, uses rubric titles', async () => {
  profiles = [v1, v2]
  mockSession(['jobprofile.edit', 'directory.view'])
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: {} } as never)
  render(renderAt('/career-paths/v2', routes))

  await screen.findByRole('button', { name: 'Remove SQL' })
  const skill = screen.getByRole('combobox', { name: 'Skill' })
  const names = within(skill)
    .getAllByRole('option')
    .map((o) => o.textContent)
  expect(names).toEqual(['Add a skill…', 'Python'])

  fireEvent.change(skill, { target: { value: 's-py' } })
  expect(await screen.findByRole('option', { name: '3 · Ships pipelines' })).toBeInTheDocument()
  fireEvent.change(screen.getByRole('combobox', { name: 'Minimum level' }), {
    target: { value: '3' },
  })
  fireEvent.change(screen.getByRole('combobox', { name: 'Criticality' }), {
    target: { value: 'supporting' },
  })
  fireEvent.click(screen.getByRole('button', { name: 'Add requirement' }))

  await vi.waitFor(() =>
    expect(post).toHaveBeenCalledWith('/profiles/job-profiles/v2/requirements/', {
      skill: 's-py',
      min_level: 3,
      criticality: 'supporting',
    }),
  )
})

test('publishing needs an explicit confirm', async () => {
  profiles = [v1, v2]
  mockSession(['jobprofile.edit', 'directory.view'])
  const post = vi
    .spyOn(api, 'post')
    .mockResolvedValue({ data: { ...v2, status: 'published' } } as never)
  render(renderAt('/career-paths/v2', routes))

  fireEvent.click(await screen.findByRole('button', { name: 'Publish v2' }))
  expect(post).not.toHaveBeenCalled()
  const dialog = screen.getByRole('alertdialog')
  expect(dialog).toHaveTextContent(/stays pinned to v1/)

  fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel' }))
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
  expect(post).not.toHaveBeenCalled()

  fireEvent.click(screen.getByRole('button', { name: 'Publish v2' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm publish' }))
  await vi.waitFor(() => expect(post).toHaveBeenCalledWith('/profiles/job-profiles/v2/publish/'))
})

test('a conflict from the server is shown, not swallowed', async () => {
  profiles = [v1, v2]
  mockSession(['jobprofile.edit', 'directory.view'])
  const { AxiosError } = await import('axios')
  vi.spyOn(api, 'post').mockRejectedValue(
    new AxiosError('409', 'ERR', undefined, undefined, {
      status: 409,
      data: {
        error: { code: 'profile_not_editable', detail: 'Retired profiles can’t be published.' },
      },
    } as never),
  )
  render(renderAt('/career-paths/v2', routes))
  fireEvent.click(await screen.findByRole('button', { name: 'Publish v2' }))
  fireEvent.click(screen.getByRole('button', { name: 'Confirm publish' }))
  expect(await screen.findByRole('alert')).toHaveTextContent('Retired profiles can’t be published.')
})

test('without jobprofile.edit the editor explains what is missing', () => {
  mockSession(['directory.view'])
  render(renderAt('/career-paths/v1', routes))
  expect(screen.getByText(/jobprofile.edit/)).toBeInTheDocument()
})

test('an armed confirm does not follow you to another version', async () => {
  profiles = [v1, v2]
  mockSession(['jobprofile.edit', 'directory.view'])
  render(renderAt('/career-paths/v2', routes))

  // The version history links to the version you're not on. Visit v1 and come back
  // so both are cached and switching no longer passes through a loading state.
  const switchVersion = async (leaving: string) => {
    fireEvent.click(await screen.findByRole('link', { name: 'Open' }))
    await vi.waitFor(() =>
      expect(screen.queryByRole('button', { name: leaving })).not.toBeInTheDocument(),
    )
  }
  await screen.findByRole('button', { name: 'Publish v2' })
  await switchVersion('Publish v2')
  await switchVersion('Edit as new version')
  await screen.findByRole('button', { name: 'Publish v2' })

  fireEvent.click(screen.getByRole('button', { name: 'Publish v2' }))
  expect(screen.getByRole('alertdialog')).toBeInTheDocument()
  await switchVersion('Publish v2')
  fireEvent.click(await screen.findByRole('link', { name: 'Open' }))

  expect(await screen.findByRole('button', { name: 'Publish v2' })).toBeInTheDocument()
  expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
})
