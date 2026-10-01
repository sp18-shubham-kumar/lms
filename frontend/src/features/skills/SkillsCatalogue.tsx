/**
 * The skill catalogue, "Path" style: a grid of skills the learner can add to
 * their route. Static fixture data for now (see fixtures.ts).
 */
import { demoSkills } from './fixtures'
import { SkillCard } from './components/SkillCard'

export function SkillsCatalogue() {
  const skills = demoSkills
  const onRouteCount = skills.filter((s) => s.onRoute).length

  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">Skills</h1>
      <p className="mt-1 text-sm text-ink-soft">
        Browse the catalogue and add skills to your route. {onRouteCount} already on your path.
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {skills.map((skill) => (
          <SkillCard key={skill.id} skill={skill} />
        ))}
      </div>
    </section>
  )
}
