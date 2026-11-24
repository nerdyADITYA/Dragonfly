import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'

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

// Live events drive updates; polling while something is in flight is only a fallback. No fake progress (§34).
export const ACTIVE = new Set(['queued', 'running'])
export const pollWhileActive = (q) => (ACTIVE.has(q.state.data?.status) ? 5000 : false)

/** Subscribe to a project's live events; refetch every query whose key mentions an id in the event. */
export function useLiveEvents(projectId) {
  const qc = useQueryClient()
  const [last, setLast] = useState(null)
  useEffect(() => {
    if (!projectId) return
    let ws, retry, closed = false, delay = 1000
    const connect = () => {
      ws = new WebSocket(`${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/v1/ws/projects/${projectId}`)
      ws.onopen = () => { delay = 1000 }
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data)
        const ids = new Set(Object.values(ev).filter((v) => typeof v === 'string'))
        qc.invalidateQueries({ predicate: (q) => q.queryKey.some((k) => ids.has(k)) || q.queryKey[0] === 'dashboard' })
        setLast(ev)
      }
      ws.onclose = () => { if (!closed) retry = setTimeout(connect, (delay = Math.min(delay * 2, 30000))) }
    }
    connect()
    return () => { closed = true; clearTimeout(retry); ws?.close() }
  }, [projectId, qc])
  return last
}
