/** Composes the app-wide providers around the router. */
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'

import { AuthProvider } from './lib/auth'
import { queryClient } from './lib/queryClient'
import { router } from './router'
import { TenantProvider } from './lib/tenant'

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <TenantProvider>
          <RouterProvider router={router} />
        </TenantProvider>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
