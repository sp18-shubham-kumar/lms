/**
 * Route table.
 *
 * Public: /login, /choose. Everything else is behind auth and rendered inside
 * the AppShell (one shell, capability-gated sections).
 */
import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AdminPage } from './pages/AdminPage'
import { ChooseTenantPage } from './pages/ChooseTenantPage'
import { DashboardPage } from './pages/DashboardPage'
import { DirectoryPage } from './pages/DirectoryPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { ProfilePage } from './pages/ProfilePage'
import { SkillsPage } from './pages/SkillsPage'
import { TeamPage } from './pages/TeamPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/choose', element: <ChooseTenantPage /> },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/directory', element: <DirectoryPage /> },
          { path: '/people/:personId', element: <ProfilePage /> },
          { path: '/skills', element: <SkillsPage /> },
          { path: '/team', element: <TeamPage /> },
          { path: '/admin', element: <AdminPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
