/**
 * The learner's progress actions, shared by every screen that shows a resource
 * card: start a resource, or mark its next module done (the backend completes
 * the resource when the last module is marked).
 */
import { useStartResource, useUpdateProgress } from './api'
import type { LearningProgress } from './types'

export function useProgressActions() {
  const start = useStartResource()
  const update = useUpdateProgress()
  return {
    busy: start.isPending || update.isPending,
    start: (resourceId: string) => start.mutate(resourceId),
    markModuleDone: (progress: LearningProgress) =>
      update.mutate({ id: progress.id, completed_modules: progress.completed_modules + 1 }),
  }
}
