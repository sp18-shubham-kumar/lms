import { useTenant } from './tenant'

/** The active tenant's id, the scope every tenant query key carries. */
export function useTenantId(): string | undefined {
  return useTenant().tenant?.id
}
