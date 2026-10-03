import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import type { LearningProgress, ResourceSummary } from '../types'
import { ResourceCard } from './ResourceCard'

const resource: ResourceSummary = {
  id: 'r1',
  title: 'Intermediate Python for Data',
  kind: 'course',
  url: 'https://example.test/python',
  provider: 'Acme Academy',
  module_count: 6,
  duration_minutes: 240,
  status: 'published',
}

const progress = (overrides: Partial<LearningProgress> = {}): LearningProgress => ({
  id: 'lp1',
  resource: 'r1',
  resource_detail: resource,
  status: 'in_progress',
  completed_modules: 2,
  started_at: '2026-10-01T00:00:00Z',
  completed_at: null,
  updated_at: '2026-10-01T00:00:00Z',
  ...overrides,
})

function renderCard(props: Partial<Parameters<typeof ResourceCard>[0]> = {}) {
  const handlers = { onStart: vi.fn(), onModuleDone: vi.fn() }
  render(<ResourceCard resource={resource} canLearn {...handlers} {...props} />)
  return handlers
}

test('an unstarted resource offers Start', () => {
  const { onStart } = renderCard()
  expect(screen.getByText('Course · 4 h · 6 modules')).toBeInTheDocument()
  fireEvent.click(screen.getByRole('button', { name: 'Start' }))
  expect(onStart).toHaveBeenCalledOnce()
})

test('an in-progress resource shows modules done, continue, and mark-done', () => {
  const current = progress()
  const { onModuleDone } = renderCard({ progress: current })
  expect(screen.getByText('Course · 4 h · 2 of 6 modules')).toBeInTheDocument()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '33')
  expect(screen.getByRole('link', { name: 'Continue module 3' })).toHaveAttribute(
    'href',
    resource.url,
  )
  fireEvent.click(screen.getByRole('button', { name: 'Mark module 3 done' }))
  expect(onModuleDone).toHaveBeenCalledWith(current)
})

test('a completed resource has no progress actions', () => {
  renderCard({ progress: progress({ status: 'completed', completed_modules: 6 }) })
  expect(screen.getByText('Completed')).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
})

test('a viewer who cannot record progress only gets the link', () => {
  renderCard({ canLearn: false })
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(screen.getByRole('link', { name: /Open/ })).toBeInTheDocument()
})
