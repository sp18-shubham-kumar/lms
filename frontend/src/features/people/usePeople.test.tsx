import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { expect, test, vi } from 'vitest'

import { api } from '../../lib/api'
import { usePeople } from './usePeople'

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
