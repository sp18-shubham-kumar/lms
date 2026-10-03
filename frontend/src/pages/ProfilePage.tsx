import { useParams } from 'react-router-dom'

import { PersonProfile } from '../features/people/PersonProfile'

export function ProfilePage() {
  const { personId = 'me' } = useParams()
  return <PersonProfile key={personId} personId={personId} />
}
