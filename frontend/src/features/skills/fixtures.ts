/**
 * Static demo data for the skill catalogue. MOCK ONLY — no network.
 * Swap for a `useSkills()` TanStack Query hook when the backend is ready.
 */
import type { CatalogueSkill } from './types'

export const demoSkills: CatalogueSkill[] = [
  { id: 'dbt', name: 'dbt', domain: 'Data transformation', myLevel: 1, onRoute: true, requiredForTarget: true },
  { id: 'kafka', name: 'Kafka', domain: 'Streaming', myLevel: 0, onRoute: true, requiredForTarget: true },
  { id: 'python', name: 'Python', domain: 'Programming', myLevel: 2, onRoute: true, requiredForTarget: true },
  { id: 'sql', name: 'SQL', domain: 'Data', myLevel: 3, onRoute: false, requiredForTarget: true },
  { id: 'airflow', name: 'Airflow', domain: 'Orchestration', myLevel: 2, onRoute: false, requiredForTarget: true },
  { id: 'terraform', name: 'Terraform', domain: 'Infrastructure', myLevel: 0, onRoute: false, requiredForTarget: false },
  { id: 'spark', name: 'Spark', domain: 'Big data', myLevel: 1, onRoute: false, requiredForTarget: false },
  { id: 'data-modeling', name: 'Data modeling', domain: 'Data', myLevel: 3, onRoute: false, requiredForTarget: true },
]
