import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, expect, test, vi } from 'vitest'

import { mockSession } from '../test/utils'
import { AppShell } from './AppShell'
import { CapabilityGate } from './CapabilityGate'

afterEach(() => vi.restoreAllMocks())

test('gate hides content from callers without the capability', () => {
  mockSession(['skill.verify'])
  render(
    <>
      <CapabilityGate capability="taxonomy.edit">framework</CapabilityGate>
      <CapabilityGate capability="skill.verify">queue</CapabilityGate>
    </>,
  )
  expect(screen.queryByText('framework')).not.toBeInTheDocument()
  expect(screen.getByText('queue')).toBeInTheDocument()
  expect(screen.getByText('You don’t have access to this page.')).toBeInTheDocument()
})

test('Framework and Verify nav items follow their capabilities', () => {
  mockSession(['taxonomy.edit'])
  render(
    <MemoryRouter>
      <AppShell />
    </MemoryRouter>,
  )
  expect(screen.getByRole('link', { name: 'Framework' })).toHaveAttribute('href', '/framework')
  expect(screen.queryByRole('link', { name: 'Verify' })).not.toBeInTheDocument()
})
