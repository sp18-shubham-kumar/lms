/**
 * TanStack Query client.
 *
 * Server state is cached per (tenant + resource). NEVER let cache survive a
 * tenant switch — `resetForTenantSwitch()` clears everything and must be called
 * from the tenant picker before navigating into the new tenant.
 */
import { QueryClient } from '@tanstack/react-query'

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
})

export function resetForTenantSwitch(): void {
  queryClient.clear()
}
