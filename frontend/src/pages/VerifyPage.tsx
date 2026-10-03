import { CapabilityGate } from '../components/CapabilityGate'
import { VerifyQueue } from '../features/verify/VerifyQueue'

export function VerifyPage() {
  return (
    <CapabilityGate capability="skill.verify">
      <VerifyQueue />
    </CapabilityGate>
  )
}
