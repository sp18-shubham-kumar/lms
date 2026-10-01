import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import { RoadmapHome } from './RoadmapHome'

test('shows the target grade, readiness, and the current step with its next resource', () => {
  render(<RoadmapHome />)

  expect(screen.getByRole('heading', { name: /Data Engineer · L2/ })).toBeInTheDocument()
  expect(screen.getByLabelText(/Readiness 68 percent/)).toBeInTheDocument()

  // The current step is raised with its "do this next" resource.
  expect(screen.getByText(/Now · Python → Proficient/)).toBeInTheDocument()
  expect(screen.getByText('Intermediate Python for Data')).toBeInTheDocument()

  // The first upcoming step is labelled "Next", later ones "Then".
  expect(screen.getByText(/Next · dbt → Working/)).toBeInTheDocument()
  expect(screen.getByText(/Then · Kafka → Aware/)).toBeInTheDocument()
})
