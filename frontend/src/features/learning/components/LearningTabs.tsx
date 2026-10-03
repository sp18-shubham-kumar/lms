/** Header and tab strip for the learning area; Manage only shows for resource.edit. */
import { NavLink } from 'react-router-dom'

import { useAuth } from '../../../lib/auth'

const TAB = 'rounded-md px-3 py-1.5 text-sm font-medium'

export function LearningTabs() {
  const { hasCapability } = useAuth()
  const tabs = [
    { to: '/learning', label: 'Library' },
    ...(hasCapability('resource.edit') ? [{ to: '/learning/manage', label: 'Manage' }] : []),
  ]
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-ink">Learning</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Courses, articles and videos linked to the skills on your path.
      </p>
      {tabs.length > 1 && (
        <nav className="mt-4 flex gap-1 border-b border-brand-100 pb-2">
          {tabs.map((tab) => (
            <NavLink
              key={tab.to}
              to={tab.to}
              end
              className={({ isActive }) =>
                isActive ? `${TAB} bg-brand-50 text-ink` : `${TAB} text-ink-soft hover:text-ink`
              }
            >
              {tab.label}
            </NavLink>
          ))}
        </nav>
      )}
    </div>
  )
}
