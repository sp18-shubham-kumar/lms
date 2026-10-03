import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { toPeopleParams, usePeople } from './usePeople'

vi.mock('../../lib/tenant', () => ({ useTenant: () => ({ tenant: { id: 't1', name: 'Acme' } }) }))

test('usePeople fetches the people page', async () => {
  vi.spyOn(api, 'get').mockResolvedValue({
    data: {
      count: 1,
      next: null,
      previous: null,
      results: [
        { id: 'p1', email: 'a@a.test', display_name: 'A', org_unit: null, status: 'active' },
      ],
    },
  } as never)
  const client = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => usePeople(1), { wrapper })
  await waitFor(() => expect(result.current.data?.results[0].email).toBe('a@a.test'))
})

test('toPeopleParams drops blanks, trims search, and ignores level without a skill', () => {
  expect(toPeopleParams({ q: '  ann ', level: 3, org_unit: '' })).toEqual({ q: 'ann' })
  expect(toPeopleParams({ skill: 's1', level: 2, org_unit: 'o1' })).toEqual({
    skill: 's1',
    level: 2,
    org_unit: 'o1',
  })
})

test('usePeople sends the filters and page size to the API', async () => {
  const get = vi
    .spyOn(api, 'get')
    .mockResolvedValue({ data: { count: 0, next: null, previous: null, results: [] } } as never)
  const client = new QueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  const { result } = renderHook(() => usePeople(2, { skill: 's1', level: 3 }, 50), { wrapper })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(get).toHaveBeenCalledWith('/identity/people/', {
    params: { page: 2, skill: 's1', level: 3, page_size: 50 },
  })
})
