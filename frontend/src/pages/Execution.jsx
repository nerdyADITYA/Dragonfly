import { useMutation, useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, artifactUrl, pollWhileActive } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Loading } from '../ui.jsx'
import { describeStep } from './TestCases.jsx'

const List = ({ title, items, render }) => (
  <div>
    <p className="font-semibold">{title} ({items.length})</p>
    {items.length === 0 ? <p className="text-slate-500">none</p> : <ul className="max-h-40 overflow-auto font-mono">{items.map((x, i) => <li key={i}>{render(x)}</li>)}</ul>}
  </div>
)

export default function Execution() {
  const { id } = useParams()
  const nav = useNavigate()
  const ex = useQuery({ queryKey: ['ex', id], queryFn: () => api(`/test-executions/${id}`), refetchInterval: pollWhileActive })
  const rerun = useMutation({ mutationFn: () => api(`/test-executions/${id}/rerun`, { method: 'POST' }), onSuccess: (r) => nav(`/runs/${r.id}`) })
  if (ex.isLoading) return <Loading />
  if (ex.error) return <ErrorBox error={ex.error} />
  const e = ex.data
  const d = e.definition_snapshot
  const ev = e.execution_metadata_json?.browser_events || { console_errors: [], page_errors: [], failed_requests: [], blocked_requests: [] }
  const trace = e.artifacts.find((a) => a.artifact_type === 'trace')
  return (
    <>
      <Link to={`/runs/${e.test_run_id}`} className="text-sm text-indigo-700">← Test run</Link>
      <Card title={<>{d.key} — {d.title} <Badge>{e.status}</Badge></>} actions={<Button variant="secondary" onClick={() => rerun.mutate()}>Re-run</Button>}>
        <ErrorBox error={rerun.error} />
        {e.failure_message && <p className="rounded bg-red-50 p-2 text-sm text-red-800"><strong>{e.failure_type}</strong>: {e.failure_message}</p>}
        <p className="mt-1 text-xs text-slate-500">
          Attempt {e.attempt_number} · test v{e.test_case_version} · {e.duration_ms != null && `${(e.duration_ms / 1000).toFixed(1)}s`} ·{' '}
          {e.execution_metadata_json?.browser} {e.execution_metadata_json?.viewport?.join('×')} · {e.execution_metadata_json?.environment}
          {trace && <> · <a className="text-indigo-700" href={artifactUrl(trace.id)}>download Playwright trace</a> (open with <code>npx playwright show-trace</code>)</>}
        </p>
      </Card>

      <Card title="Steps">
        <ol className="space-y-3">
          {e.steps.map((s) => (
            <li key={s.step_number} className={`rounded border p-2 text-sm ${s.status === 'failed' ? 'border-red-300 bg-red-50' : s.status === 'skipped' ? 'border-slate-200 opacity-60' : 'border-slate-200'}`}>
              <div className="flex items-center gap-2">
                <span className="w-6 text-xs text-slate-400">{s.step_number}</span>
                <span className="flex-1">{describeStep(s.action_definition_json)}</span>
                <span className="text-xs text-slate-500">{s.duration_ms}ms</span>
                <Badge>{s.status}</Badge>
              </div>
              {s.error_message && <pre className="mt-1 overflow-auto whitespace-pre-wrap text-xs text-red-800">{s.error_message}</pre>}
              {s.screenshot_artifact_id && (
                <a href={artifactUrl(s.screenshot_artifact_id)} target="_blank" rel="noreferrer">
                  <img src={artifactUrl(s.screenshot_artifact_id)} alt={`Screenshot after step ${s.step_number}`} className="mt-2 max-h-64 rounded border" />
                </a>
              )}
            </li>
          ))}
        </ol>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Assertions">
          {e.assertion_results_json.length === 0 && <Empty>No assertions evaluated.</Empty>}
          <ul className="space-y-1 text-sm">
            {e.assertion_results_json.map((a, i) => (
              <li key={i}>
                <Badge>{a.passed ? 'passed' : 'failed'}</Badge> step {a.step} {a.type}: expected {String(a.expected)}
                {a.actual != null && <span className="text-slate-600"> · actual <code>{String(a.actual).slice(0, 200)}</code></span>}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Browser evidence">
          <div className="space-y-2 text-xs">
            <List title="Page errors" items={ev.page_errors} render={(x) => x} />
            <List title="Console errors" items={ev.console_errors} render={(x) => x} />
            <List title="Failed requests" items={ev.failed_requests} render={(x) => `${x.status ?? x.error} ${x.method || ''} ${x.url}`} />
            <List title="Blocked by scope" items={ev.blocked_requests} render={(x) => `${x.url} — ${x.reason}`} />
          </div>
        </Card>
      </div>
    </>
  )
}
