/**
 * Types for the skill catalogue. In the "Path" direction the catalogue reads as
 * "things you can add to your route", not a course list.
 *
 * UI-facing shapes; a `useSkills()` hook returns these once the backend lands.
 */
import type { LevelValue } from '../roadmap/types'

export interface CatalogueSkill {
  id: string
  name: string
  domain: string
  /** The learner's current level, or 0 if never declared. */
  myLevel: LevelValue
  /** Whether this skill is already on the learner's roadmap. */
  onRoute: boolean
  /** Whether the target grade requires this skill. */
  requiredForTarget: boolean
}
