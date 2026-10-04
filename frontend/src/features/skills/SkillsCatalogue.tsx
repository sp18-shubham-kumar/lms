/**
 * The skill catalogue, wired to the API. Lists tenant + global skills grouped by
 * domain; a learner can declare/remove their own skills (the self-claimed tier).
 */
import { useAuth } from '../../lib/auth'
import {
  useSkillDomains,
  useSkills,
  useMyDeclarations,
  useDeclareSkill,
  useRemoveDeclaration,
} from './api'
import { SkillCard } from './components/SkillCard'

export function SkillsCatalogue() {
  const { hasCapability } = useAuth()
  const canDeclare = hasCapability('skill.claim.submit')

  const skills = useSkills()
  const domains = useSkillDomains()
  const declarations = useMyDeclarations()
  const declare = useDeclareSkill()
  const remove = useRemoveDeclaration()

  if (skills.isLoading || domains.isLoading) {
    return <p className="text-ink-soft">Loading skills…</p>
  }
  if (skills.isError) {
    return <p className="text-ink-soft">Could not load the skill catalogue.</p>
  }

  const domainName = new Map((domains.data ?? []).map((d) => [d.id, d.name]))
  const myLevel = new Map((declarations.data ?? []).map((d) => [d.skill, d]))
  const declaredCount = declarations.data?.length ?? 0
  const busy = declare.isPending || remove.isPending

  return (
    <section className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-bold tracking-tight text-ink">Skills</h1>
      <p className="mt-1 text-sm text-ink-soft">
        {canDeclare
          ? `Browse the catalogue and declare your skills. ${declaredCount} declared.`
          : 'Browse the skill catalogue.'}
      </p>

      <div className="mt-5 grid gap-3 sm:grid-cols-2">
        {(skills.data ?? []).map((skill) => (
          <SkillCard
            key={skill.id}
            skill={skill}
            domainName={domainName.get(skill.domain) ?? '—'}
            declaration={myLevel.get(skill.id)}
            canDeclare={canDeclare}
            busy={busy}
            onDeclare={(level) => declare.mutate({ skill: skill.id, level })}
            onRemove={(id) => remove.mutate(id)}
          />
        ))}
      </div>
    </section>
  )
}
