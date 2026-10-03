import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import type { ReactNode } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import * as authModule from '../../lib/auth'
import * as tenantModule from '../../lib/tenant'
import { ResourceLibrary } from './ResourceLibrary'
import { ResourceManager } from './ResourceManager'

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

const page = (results: unknown[]) => ({
  data: { count: results.length, next: null, previous: null, results },
})

const python = {
  id: 's1',
  tenant: null,
  domain: 'd1',
  name: 'Python',
  slug: 'python',
  external_code: '',
  description: '',
  status: 'published',
  version: 1,
}

const course = {
  id: 'r1',
  title: 'Intermediate Python for Data',
  kind: 'course',
  url: '',
  provider: 'Acme Academy',
  description: '',
  module_count: 6,
  duration_minutes: 240,
  status: 'published',
  skills: [{ skill: 's1', skill_name: 'Python', level: 2 }],
  created_at: '',
  updated_at: '',
}
const article = { ...course, id: 'r2', title: 'Window Functions in Practice', kind: 'article' }

const myProgress = {
  id: 'lp1',
  resource: 'r1',
  resource_detail: course,
  status: 'in_progress',
  completed_modules: 2,
  started_at: '2026-10-01T00:00:00Z',
  completed_at: null,
  updated_at: '2026-10-01T00:00:00Z',
}

let caps: string[]
let getSpy: ReturnType<typeof vi.spyOn>

beforeEach(() => {
  caps = ['directory.view', 'skill.claim.submit']
  vi.spyOn(authModule, 'useAuth').mockReturnValue({
    hasCapability: (cap: string) => caps.includes(cap),
  } as never)
  vi.spyOn(tenantModule, 'useTenant').mockReturnValue({
    tenant: { id: 't1', name: 'Acme' },
    setTenant: vi.fn(),
  } as never)
  getSpy = vi.spyOn(api, 'get').mockImplementation((async (url: string) => {
    if (url === '/skills/') return page([python])
    if (url === '/learning/me/progress/') return page([myProgress])
    return page([course, article])
  }) as never)
})

test('the library shows the learner progress and every resource', async () => {
  render(wrap(<ResourceLibrary />))
  expect(await screen.findByText('1 in progress · 0 completed')).toBeInTheDocument()
  expect(await screen.findByText('Window Functions in Practice')).toBeInTheDocument()
  // The in-progress course appears under "Your learning" and in the library.
  expect(screen.getAllByText('Intermediate Python for Data')).toHaveLength(2)
  expect(screen.getAllByRole('button', { name: 'Mark module 3 done' })).toHaveLength(2)
  expect(screen.queryByRole('link', { name: 'Manage' })).not.toBeInTheDocument()
})

test('filtering by skill queries the library for that skill', async () => {
  render(wrap(<ResourceLibrary />))
  await screen.findByRole('option', { name: 'Python' })
  fireEvent.change(screen.getByLabelText('Skill'), { target: { value: 's1' } })
  await waitFor(() =>
    expect(getSpy).toHaveBeenCalledWith('/learning/resources/', {
      params: { page_size: 200, skill: 's1' },
    }),
  )
})

test('starting a resource posts progress for it', async () => {
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: myProgress } as never)
  render(wrap(<ResourceLibrary />))
  const card = (await screen.findByText('Window Functions in Practice')).closest('div.rounded-lg')!
  fireEvent.click(within(card as HTMLElement).getByRole('button', { name: 'Start' }))
  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/learning/me/progress/', { resource: 'r2' }),
  )
})

test('marking a module done patches the next module count', async () => {
  const patch = vi.spyOn(api, 'patch').mockResolvedValue({ data: myProgress } as never)
  render(wrap(<ResourceLibrary />))
  fireEvent.click((await screen.findAllByRole('button', { name: 'Mark module 3 done' }))[0])
  await waitFor(() =>
    expect(patch).toHaveBeenCalledWith('/learning/me/progress/lp1/', { completed_modules: 3 }),
  )
})

test('the manage screen is closed to members without resource.edit', () => {
  render(wrap(<ResourceManager />))
  expect(screen.getByText(/don’t have permission to manage/)).toBeInTheDocument()
  expect(getSpy).not.toHaveBeenCalledWith('/learning/resources/', expect.anything())
})

test('an editor creates a resource with its skill links', async () => {
  caps = [...caps, 'resource.edit']
  const post = vi.spyOn(api, 'post').mockResolvedValue({ data: course } as never)
  render(wrap(<ResourceManager />))
  expect(await screen.findByRole('link', { name: 'Manage' })).toBeInTheDocument()
  await screen.findByText('Window Functions in Practice')

  fireEvent.click(screen.getByRole('button', { name: 'New resource' }))
  const form = screen.getByRole('form', { name: 'New resource' })
  fireEvent.change(within(form).getByLabelText('Title'), { target: { value: 'dbt Fundamentals' } })
  fireEvent.change(within(form).getByLabelText('Modules'), { target: { value: '5' } })
  fireEvent.click(within(form).getByRole('button', { name: '+ Add skill' }))
  fireEvent.change(within(form).getByLabelText('Level'), { target: { value: '3' } })
  fireEvent.click(within(form).getByRole('button', { name: 'Create resource' }))

  await waitFor(() =>
    expect(post).toHaveBeenCalledWith('/learning/resources/', {
      title: 'dbt Fundamentals',
      kind: 'course',
      url: '',
      provider: '',
      description: '',
      module_count: 5,
      duration_minutes: null,
      status: 'draft',
      skills: [{ skill: 's1', level: 3 }],
    }),
  )
  await waitFor(() =>
    expect(screen.queryByRole('form', { name: 'New resource' })).not.toBeInTheDocument(),
  )
})

test('archiving asks for confirmation and deletes the resource', async () => {
  caps = [...caps, 'resource.edit']
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const del = vi.spyOn(api, 'delete').mockResolvedValue({ data: null } as never)
  render(wrap(<ResourceManager />))
  fireEvent.click((await screen.findAllByRole('button', { name: 'Archive' }))[0])
  await waitFor(() => expect(del).toHaveBeenCalledWith('/learning/resources/r1/'))
})
