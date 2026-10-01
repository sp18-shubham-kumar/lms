import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { SkillsCatalogue } from './SkillsCatalogue'

test('lists skills and lets you add one to your route', () => {
  render(<SkillsCatalogue />)

  expect(screen.getByRole('heading', { name: 'Skills' })).toBeInTheDocument()

  // Terraform starts off-route, so it offers an "add" action.
  const addButtons = screen.getAllByRole('button', { name: /Add to route/ })
  expect(addButtons.length).toBeGreaterThan(0)

  // Adding one flips it to the on-path marker.
  const before = screen.getAllByText(/On your path/).length
  fireEvent.click(addButtons[0])
  expect(screen.getAllByText(/On your path/).length).toBe(before + 1)
})
