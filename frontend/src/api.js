export async function api(path, { method = 'GET', body } = {}) {
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 204) return null
  const data = await res.json().catch(() => null)
  if (!res.ok) {
    const d = data?.detail
    throw new Error(typeof d === 'string' ? d : Array.isArray(d) ? d.map((e) => `${e.loc?.slice(-1)}: ${e.msg}`).join('; ') : `HTTP ${res.status}`)
  }
  return data
}

export const artifactUrl = (id) => `/api/v1/artifacts/${id}`

// Poll while something is still in flight; no fake progress (§34).
export const ACTIVE = new Set(['queued', 'running'])
export const pollWhileActive = (q) => (ACTIVE.has(q.state.data?.status) ? 1500 : false)
