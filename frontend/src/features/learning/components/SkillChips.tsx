/** The skills a resource teaches, as small "SQL · L2" chips. */
import type { ResourceSkillLink } from '../types'

export function SkillChips({ links }: { links: ResourceSkillLink[] }) {
  if (!links.length) return null
  return (
    <ul className="mt-1.5 flex flex-wrap gap-1 pl-11">
      {links.map((link) => (
        <li
          key={link.skill}
          className="rounded-full border border-brand-100 bg-white px-2 py-0.5 font-mono text-[10px] text-ink-soft"
        >
          {link.skill_name} · L{link.level}
        </li>
      ))}
    </ul>
  )
}
