/**
 * Route table.
 *
 * Public: /login, /invite/accept. Behind auth but outside the AppShell (no active
 * tenant): /choose and /platform. Everything else renders inside the AppShell
 * (one shell, capability-gated sections).
 */
import { createBrowserRouter } from 'react-router-dom'

import { AppShell } from './components/AppShell'
import { ProtectedRoute } from './components/ProtectedRoute'
import { AcceptInvitePage } from './pages/AcceptInvitePage'
import { AdminPage } from './pages/AdminPage'
import { ChooseTenantPage } from './pages/ChooseTenantPage'
import { DashboardPage } from './pages/DashboardPage'
import { DirectoryPage } from './pages/DirectoryPage'
import { FrameworkPage } from './pages/FrameworkPage'
import { LoginPage } from './pages/LoginPage'
import { NotFoundPage } from './pages/NotFoundPage'
import { PlatformPage } from './pages/PlatformPage'
import { ProfilePage } from './pages/ProfilePage'
import { SkillEditorPage } from './pages/SkillEditorPage'
import { SkillsPage } from './pages/SkillsPage'
import { TeamPage } from './pages/TeamPage'
import { VerifyPage } from './pages/VerifyPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/invite/accept', element: <AcceptInvitePage /> },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/choose', element: <ChooseTenantPage /> },
      { path: '/platform', element: <PlatformPage /> },
      {
        element: <AppShell />,
        children: [
          { path: '/', element: <DashboardPage /> },
          { path: '/directory', element: <DirectoryPage /> },
          { path: '/people/:personId', element: <ProfilePage /> },
          { path: '/skills', element: <SkillsPage /> },
          { path: '/team', element: <TeamPage /> },
          { path: '/framework', element: <FrameworkPage /> },
          { path: '/framework/skills/:id', element: <SkillEditorPage /> },
          { path: '/verify', element: <VerifyPage /> },
          { path: '/admin', element: <AdminPage /> },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
