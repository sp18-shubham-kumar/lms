/**
 * Route table.
 *
 * Public: /login, /choose. Everything else is behind auth and rendered inside
 * the AppShell (one shell, capability-gated sections).
 */
import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { CareerPathsPage } from './features/career-paths/CareerPathsPage'
import { JobProfileDetail } from './features/career-paths/JobProfileDetail'
import { MemberReadinessPage } from './features/team/MemberReadinessPage'
import { AdminPage } from './pages/AdminPage'
import { ChooseTenantPage } from './pages/ChooseTenantPage'
import { DashboardPage } from './pages/DashboardPage'
import { DirectoryPage } from './pages/DirectoryPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
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
          { path: '/skills', element: <SkillsPage /> },
          { path: '/team', element: <TeamPage /> },
          { path: '/team/members/:membershipId', element: <MemberReadinessPage /> },
          { path: '/career-paths', element: <CareerPathsPage /> },
          { path: '/career-paths/:id', element: <JobProfileDetail /> },
          { path: '/admin', element: <AdminPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
