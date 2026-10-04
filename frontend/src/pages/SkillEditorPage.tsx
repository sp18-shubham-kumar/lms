import { useParams } from 'react-router-dom'

import { CapabilityGate } from '../components/CapabilityGate'
import { SkillEditor } from '../features/framework/SkillEditor'

export function SkillEditorPage() {
  const { id } = useParams()
  return (
    <CapabilityGate capability="taxonomy.edit">
      {/* Keyed on the id so opening another version starts with fresh tab and save state. */}
      <SkillEditor key={id} />
    </CapabilityGate>
  )
}
