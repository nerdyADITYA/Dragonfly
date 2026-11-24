import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { ACTIVE, api, pollWhileActive, useLiveEvents } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Loading, fmt } from '../ui.jsx'

export default function Run() {
  const { id } = useParams()
  const qc = useQueryClient()
  const run = useQuery({ queryKey: ['run', id], queryFn: () => api(`/test-runs/${id}`), refetchInterval: pollWhileActive })
  useLiveEvents(run.data?.project_id)
  const cancel = useMutation({ mutationFn: () => api(`/test-runs/${id}/cancel`, { method: 'POST' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['run', id] }) })
  if (run.isLoading) return <Loading />
  if (run.error) return <ErrorBox error={run.error} />
  const r = run.data
  return (
    <>
      <Link to={`/projects/${r.project_id}`} className="text-sm text-indigo-700">← Project</Link>
      <Card title={<>Test run <Badge>{r.status}</Badge></>} actions={ACTIVE.has(r.status) && <Button variant="danger" onClick={() => cancel.mutate()}>Cancel run</Button>}>
        <p className="text-sm text-slate-600">
          {Object.entries(r.summary_json?.counts || {}).map(([k, v]) => `${v} ${k}`).join(' · ') || `${r.executions.length} executed so far`}
        </p>
        <p className="text-xs text-slate-500">Browser {r.browser} · started {fmt(r.started_at)} · finished {fmt(r.completed_at)}</p>
      </Card>
      <Card title="Executions">
        {r.executions.length === 0 && <Empty>{ACTIVE.has(r.status) ? 'Starting…' : 'Nothing executed.'}</Empty>}
        <table className="w-full text-sm">
          <thead><tr className="text-left text-xs text-slate-500"><th>Test</th><th>Status</th><th>Failure</th><th>Attempt</th><th>Duration</th></tr></thead>
          <tbody className="divide-y divide-slate-100">
            {r.executions.map((e) => (
              <tr key={e.id}>
                <td className="py-2"><Link className="text-indigo-700 hover:underline" to={`/executions/${e.id}`}>{e.definition_snapshot.key} — {e.definition_snapshot.title}</Link></td>
                <td><Badge>{e.status}</Badge></td>
                <td className="max-w-xs truncate text-xs text-slate-600" title={e.failure_message || ''}>{e.failure_type ? `${e.failure_type}: ${e.failure_message}` : '—'}</td>
                <td>{e.attempt_number}</td>
                <td>{e.duration_ms != null ? `${(e.duration_ms / 1000).toFixed(1)}s` : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  )
}
