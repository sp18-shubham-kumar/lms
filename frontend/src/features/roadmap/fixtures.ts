/**
 * Static demo data for the roadmap.
 *
 * MOCK ONLY — no network. To wire the backend later, replace the
 * `import { demoRoadmap }` in RoadmapHome with a `useRoadmap()` TanStack Query
 * hook that returns a `Roadmap`; nothing else needs to change.
 */
import type { Roadmap } from './types'

export const demoRoadmap: Roadmap = {
  learner: 'Priya Nair',
  targetGrade: 'Data Engineer · L2',
  readiness: 68,
  milestonesCleared: 3,
  milestonesTotal: 5,
  steps: [
    {
      id: 'sql',
      skill: 'SQL',
      targetLevel: 3,
      currentLevel: 3,
      status: 'cleared',
      note: 'Cleared · verified by Anita Rao',
    },
    {
      id: 'data-modeling',
      skill: 'Data modeling',
      targetLevel: 2,
      currentLevel: 3,
      status: 'cleared',
      note: 'Cleared · exceeds target',
    },
    {
      id: 'python',
      skill: 'Python',
      targetLevel: 3,
      currentLevel: 2,
      status: 'current',
      levelsToGo: 1,
      resource: {
        title: 'Intermediate Python for Data',
        kind: 'Course',
        duration: '4h',
        modulesDone: 2,
        modulesTotal: 6,
      },
    },
    {
      id: 'dbt',
      skill: 'dbt',
      targetLevel: 2,
      currentLevel: 1,
      status: 'upcoming',
      note: '1 resource queued',
    },
    {
      id: 'kafka',
      skill: 'Kafka',
      targetLevel: 1,
      currentLevel: 0,
      status: 'upcoming',
    },
  ],
}
