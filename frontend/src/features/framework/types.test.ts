import { expect, test } from 'vitest'

import { skill } from '../../test/utils'
import type { ApiSkill } from '../skills/types'
import { isEditable, latestVersions, slugify } from './types'

test('latestVersions keeps the highest version per owner and slug', () => {
  const rows = [
    skill({ id: 'a1', version: 1, status: 'published' }),
    skill({ id: 'a2', version: 2, status: 'draft' }),
    skill({ id: 'g1', tenant: null, version: 1, status: 'published' }),
    skill({ id: 'b1', slug: 'python', name: 'Python', version: 3 }),
  ] as ApiSkill[]
  expect(latestVersions(rows).map((s) => s.id)).toEqual(['b1', 'a2', 'g1'])
})

test('only tenant drafts are editable in place', () => {
  expect(isEditable(skill() as ApiSkill)).toBe(true)
  expect(isEditable(skill({ status: 'published' }) as ApiSkill)).toBe(false)
  expect(isEditable(skill({ tenant: null }) as ApiSkill)).toBe(false)
})

test('slugify', () => {
  expect(slugify('  Data & ML Ops! ')).toBe('data-ml-ops')
})
