/** Transform an API readiness payload into the roadmap UI model. */
import type { LevelValue, Readiness, RoadmapStep } from './types'

export function toSteps(readiness: Readiness): RoadmapStep[] {
  let currentAssigned = false
  return readiness.requirements.map((r) => {
    const met = r.status === 'met'
    let status: RoadmapStep['status']
    if (met) {
      status = 'cleared'
    } else if (!currentAssigned) {
      status = 'current'
      currentAssigned = true
    } else {
      status = 'upcoming'
    }
    const currentLevel = Math.max(0, Math.min(4, r.current_level ?? 0)) as LevelValue
    const targetLevel = Math.max(1, Math.min(4, r.min_level)) as LevelValue
    return {
      id: r.skill_id,
      skill: r.skill_name,
      targetLevel,
      currentLevel,
      status,
      levelsToGo: status === 'current' ? Math.max(1, targetLevel - currentLevel) : undefined,
      note: met
        ? `Cleared · ${r.criticality}`
        : status === 'upcoming'
          ? `${r.criticality} · min ${r.min_level}`
          : undefined,
    }
  })
}
