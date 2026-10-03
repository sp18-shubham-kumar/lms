import { CapabilityGate } from '../components/CapabilityGate'
import { SkillEditor } from '../features/framework/SkillEditor'

export function SkillEditorPage() {
  return (
    <CapabilityGate capability="taxonomy.edit">
      <SkillEditor />
    </CapabilityGate>
  )
}
