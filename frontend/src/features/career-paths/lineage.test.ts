import { expect, test } from 'vitest'

import { groupLineages, latestVersions } from './lineage'
import type { JobProfile } from './types'

function profile(over: Partial<JobProfile>): JobProfile {
  return {
    id: 'id',
    tenant: 't1',
    track: 'data',
    grade: 1,
    title: 'Data Engineer L1',
    status: 'published',
    version: 1,
    created_at: '',
    updated_at: '',
    ...over,
  }
}

const l2v1 = profile({ id: 'l2v1', grade: 2, title: 'Data Engineer L2', version: 1 })
const l2v2 = profile({ id: 'l2v2', grade: 2, title: 'Data Engineer L2', version: 2 })
const l2v3 = profile({
  id: 'l2v3',
  grade: 2,
  title: 'Data Engineer L2',
  version: 3,
  status: 'draft',
})
const l1 = profile({ id: 'l1' })
const l3draft = profile({ id: 'l3', grade: 3, title: 'Data Engineer L3', status: 'draft' })

test('groups versions of one grade, newest first, ordered by grade', () => {
  const lineages = groupLineages([l2v1, l3draft, l2v3, l1, l2v2])
  expect(lineages.map((l) => l.title)).toEqual([
    'Data Engineer L1',
    'Data Engineer L2',
    'Data Engineer L3',
  ])
  const l2 = lineages[1]
  expect(l2.versions.map((v) => v.id)).toEqual(['l2v3', 'l2v2', 'l2v1'])
  expect(l2.latest.id).toBe('l2v3')
  expect(l2.latestPublished?.id).toBe('l2v2')
  expect(l2.openDraft?.id).toBe('l2v3')
})

test('same title in another track is a different lineage', () => {
  const other = profile({ id: 'x', track: 'analytics' })
  expect(groupLineages([l1, other])).toHaveLength(2)
})

test('latestVersions keeps only the newest version of each grade', () => {
  expect(latestVersions([l2v1, l2v2, l1]).map((p) => p.id)).toEqual(['l1', 'l2v2'])
})
