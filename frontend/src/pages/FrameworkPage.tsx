import { CapabilityGate } from '../components/CapabilityGate'
import { FrameworkHome } from '../features/framework/FrameworkHome'

export function FrameworkPage() {
  return (
    <CapabilityGate capability="taxonomy.edit">
      <FrameworkHome />
    </CapabilityGate>
  )
}
