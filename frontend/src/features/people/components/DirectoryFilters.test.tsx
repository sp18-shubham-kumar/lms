import { fireEvent, render, screen } from '@testing-library/react'
import { expect, test, vi } from 'vitest'

import { DirectoryFilters } from './DirectoryFilters'

const skills = [{ id: 's1', name: 'SQL' }] as never
const orgUnits = [{ id: 'o1', name: 'Data', path: 'data', parent: null }]

test('minimum level is disabled until a skill is chosen', () => {
  const { rerender } = render(
    <DirectoryFilters value={{}} onChange={vi.fn()} skills={skills} orgUnits={orgUnits} />,
  )
  expect(screen.getByLabelText('Minimum level')).toBeDisabled()
  rerender(
    <DirectoryFilters
      value={{ skill: 's1' }}
      onChange={vi.fn()}
      skills={skills}
      orgUnits={orgUnits}
    />,
  )
  expect(screen.getByLabelText('Minimum level')).toBeEnabled()
})

test('changing the skill resets the level', () => {
  const onChange = vi.fn()
  render(
    <DirectoryFilters
      value={{ skill: 's1', level: 3 }}
      onChange={onChange}
      skills={skills}
      orgUnits={orgUnits}
    />,
  )
  fireEvent.change(screen.getByLabelText('Skill'), { target: { value: '' } })
  expect(onChange).toHaveBeenCalledWith({ skill: undefined, level: undefined })
})
