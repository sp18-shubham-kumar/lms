import { LEVEL_LABELS } from '../skills/types'
import type { SkillLevel } from './types'

/**
 * "2 · Working": the rubric's own title for the level when the skill has one,
 * else the shell's generic scale (which only names 1..4).
 */
export function levelLabel(level: number, rubric?: SkillLevel[]): string {
  const title = rubric?.find((r) => r.level === level)?.title || LEVEL_LABELS[level]
  return title ? `${level} · ${title}` : `L${level}`
}
