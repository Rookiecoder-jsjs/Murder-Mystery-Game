export const API_BASE = API_BASE_URL.replace(/\/$/, '')

export function resolveAssetUrl(path?: string): string {
  if (!path) return ''
  if (/^https?:\/\//i.test(path)) return path
  return `${API_BASE}${path.startsWith('/') ? path : `/${path}`}`
}
