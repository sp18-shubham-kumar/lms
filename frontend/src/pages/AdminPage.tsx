import { PagePlaceholder } from '../components/PagePlaceholder'

export function AdminPage() {
  return (
    <PagePlaceholder
      title="Admin console"
      description="Taxonomy editor, authority grants, and member import/invite. Gated by the 'taxonomy.edit' capability. Built across Phase 1/2 (P1-R9, C13)."
      specRef="docs/specs/architecture.md · C13 Admin"
    />
  )
}
