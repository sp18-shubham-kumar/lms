/**
 * The learner's home for the "Path" direction: the gap to a target grade, drawn
 * as a route. Answers "what do I do next?" in one glance.
 *
 * Data is a static fixture for now (see fixtures.ts). Wiring the backend later
 * means swapping `demoRoadmap` for a `useRoadmap()` hook — the layout is unchanged.
 */
import { demoRoadmap } from './fixtures'
import { RoadmapSpine } from './components/RoadmapSpine'
import { ReadinessRing } from './components/ReadinessRing'

export function RoadmapHome() {
  const roadmap = demoRoadmap

  return (
    <section className="mx-auto max-w-2xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.12em] text-ink-soft">
            Your route to
          </p>
          <h1 className="mt-0.5 text-2xl font-bold tracking-tight text-ink">
            {roadmap.targetGrade}
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            {roadmap.learner} · {roadmap.milestonesCleared} of {roadmap.milestonesTotal} milestones
            cleared
          </p>
        </div>
        <ReadinessRing value={roadmap.readiness} />
      </div>

      <RoadmapSpine steps={roadmap.steps} />
    </section>
  )
}
