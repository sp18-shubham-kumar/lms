/** Where a manager drills into one member's gap against a target profile. */
export function memberReadinessPath(membershipId: string, target?: string | null): string {
  const base = `/team/members/${membershipId}`
  return target ? `${base}?target=${encodeURIComponent(target)}` : base
}
