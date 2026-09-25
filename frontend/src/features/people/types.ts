export interface DirectoryPerson {
  id: string
  email: string
  display_name: string
  org_unit: string | null
  status: string
}

export interface Paginated<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}
