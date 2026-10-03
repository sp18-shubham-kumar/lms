/** Tenant slugs, as the backend SlugField(max_length=50) accepts them. */
export const SLUG_MAX = 50

/** "Acme Data, Inc." becomes "acme-data-inc". */
export function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, SLUG_MAX)
}
