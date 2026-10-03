/**
 * Recommended resources for one gap skill on My path. Every step shares the one
 * recommendations query for the target, so a roadmap makes a single request.
 */
import { useRecommendations } from './api'
import { ResourceCard } from './components/ResourceCard'
import { useProgressActions } from './useProgressActions'

interface StepResourcesProps {
  target: string
  skillId: string
  skillName: string
  /** How many resources to show (the best-ranked first). */
  limit?: number
}

export function StepResources({ target, skillId, skillName, limit = 2 }: StepResourcesProps) {
  const recommendations = useRecommendations(target)
  const actions = useProgressActions()

  if (!recommendations.data) return null
  const gap = recommendations.data.gaps.find((g) => g.skill_id === skillId)
  const forward = gap?.resources ?? []
  // With nothing that moves the learner forward, show what the library does have
  // for the skill instead of claiming it has nothing.
  const items = (forward.length ? forward : (gap?.refreshers ?? [])).slice(0, limit)

  if (!items.length) {
    return (
      <p className="mt-2 text-[11.5px] text-ink-soft">No learning resources for {skillName} yet.</p>
    )
  }

  return (
    <div className="mt-3 space-y-2">
      {!forward.length && (
        <p className="text-[11.5px] text-ink-soft">
          No resource teaches {skillName} beyond your level {gap?.current_level} yet. A refresher at
          your level:
        </p>
      )}
      {items.map((item) => (
        <ResourceCard
          key={item.resource.id}
          resource={item.resource}
          progress={item.progress}
          canLearn
          busy={actions.busy}
          onStart={() => actions.start(item.resource.id)}
          onModuleDone={actions.markModuleDone}
        />
      ))}
    </div>
  )
}
