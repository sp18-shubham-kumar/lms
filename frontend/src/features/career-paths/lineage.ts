/**
 * Job profiles are versioned, never edited in place: every version of one grade
 * is its own row sharing (track, grade, title). A "lineage" groups those rows so
 * screens can show one grade with its version history, and pickers can offer
 * only the version learners should aim at.
 */
import type { JobProfile } from './types'

export interface Lineage {
  key: string
  track: string
  grade: number
  title: string
  /** Newest version first. */
  versions: JobProfile[]
  latest: JobProfile
  latestPublished?: JobProfile
  openDraft?: JobProfile
}

export function lineageKey(p: Pick<JobProfile, 'track' | 'grade' | 'title'>): string {
  return `${p.track}|${p.grade}|${p.title}`
}

const byVersionDesc = (a: JobProfile, b: JobProfile) => (b.version ?? 0) - (a.version ?? 0)

/** Group profiles into lineages, ordered by grade then title. */
export function groupLineages(profiles: JobProfile[]): Lineage[] {
  const groups = new Map<string, JobProfile[]>()
  for (const p of profiles) {
    const key = lineageKey(p)
    groups.set(key, [...(groups.get(key) ?? []), p])
  }
  return [...groups.entries()]
    .map(([key, rows]) => {
      const versions = [...rows].sort(byVersionDesc)
      const latest = versions[0]
      return {
        key,
        track: latest.track,
        grade: latest.grade,
        title: latest.title,
        versions,
        latest,
        latestPublished: versions.find((v) => v.status === 'published'),
        openDraft: versions.find((v) => v.status === 'draft'),
      }
    })
    .sort((a, b) => a.grade - b.grade || a.title.localeCompare(b.title))
}

/**
 * The newest version of each grade in ``profiles``. Fed only published rows,
 * that's what a learner or manager should target: an older published version
 * stays valid for snapshots pinned to it, but isn't offered as a new target.
 */
export function latestVersions(profiles: JobProfile[]): JobProfile[] {
  return groupLineages(profiles).map((l) => l.latest)
}

export function versionLabel(p: Pick<JobProfile, 'title' | 'version'>): string {
  return `${p.title} · v${p.version}`
}
