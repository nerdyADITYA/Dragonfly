import { useQuery } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'
import { api, useLiveEvents } from '../api.js'
import { Badge, Card, Empty, ErrorBox, Loading, fmt } from '../ui.jsx'

function Tile({ label, value, hint, to }) {
  const body = (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm hover:border-indigo-300">
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-2xl font-semibold">{value ?? '—'}</p>
      {hint && <p className="text-[11px] text-slate-500">{hint}</p>}
    </div>
  )
  return to ? <Link to={to}>{body}</Link> : body
}

function Trend({ days }) {
  const max = Math.max(1, ...days.map((d) => d.passed + d.failed + d.other))
  return (
    <div>
      <div className="flex h-32 items-end gap-1" role="img" aria-label="Test executions per day: passed, failed and other">
        {days.map((d) => (
          <div key={d.date} className="flex flex-1 flex-col-reverse" title={`${d.date}: ${d.passed} passed, ${d.failed} failed, ${d.other} other`}>
            <div className="bg-green-500" style={{ height: `${(d.passed / max) * 128}px` }} />
            <div className="bg-red-500" style={{ height: `${(d.failed / max) * 128}px` }} />
            <div className="bg-slate-300" style={{ height: `${(d.other / max) * 128}px` }} />
          </div>
        ))}
      </div>
      <div className="mt-1 flex justify-between text-[10px] text-slate-500"><span>{days[0]?.date}</span><span>{days.at(-1)?.date}</span></div>
      <p className="mt-1 flex gap-3 text-xs text-slate-600">
        <span><span className="inline-block h-2 w-2 bg-green-500" /> passed</span>
        <span><span className="inline-block h-2 w-2 bg-red-500" /> failed</span>
        <span><span className="inline-block h-2 w-2 bg-slate-300" /> blocked / inconclusive / other</span>
      </p>
    </div>
  )
}

export default function Dashboard() {
  const [params, setParams] = useSearchParams()
  const pid = params.get('project') || ''
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api('/projects') })
  const dash = useQuery({ queryKey: ['dashboard', pid], queryFn: () => api(`/dashboard${pid ? `?project_id=${pid}` : ''}`) })
  useLiveEvents(pid || null)

  const d = dash.data
  // Deep links only make sense inside one project; across all projects, tiles go to the project list.
  const findingsLink = (q) => (pid ? `/projects/${pid}?${q}#findings` : '/projects')
  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <select aria-label="Project" className="rounded border border-slate-300 bg-white px-2 py-1.5 text-sm" value={pid}
          onChange={(e) => setParams(e.target.value ? { project: e.target.value } : {})}>
          <option value="">All projects</option>
          {projects.data?.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
        </select>
      </div>
      {dash.isLoading && <Loading />}
      <ErrorBox error={dash.error} />
      {d && d.projects === 0 && (
        <Card><Empty>No projects yet. <Link className="text-indigo-700" to="/projects">Create your first project</Link>, add an environment, then run a discovery scan.</Empty></Card>
      )}
      {d && d.projects > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Tile label="Pass rate" value={d.pass_rate == null ? '—' : `${Math.round(d.pass_rate * 100)}%`} hint={d.pass_rate_formula} />
            <Tile label="Tests executed" value={d.executions.total}
              hint={`${d.executions.passed} passed · ${d.executions.failed} failed · ${d.executions.blocked + d.executions.inconclusive + d.executions.timed_out} blocked/inconclusive`} />
            <Tile label="Open findings" value={d.findings.open} hint={`${d.findings.total} total`} to={findingsLink('open_only=true')} />
            <Tile label="Critical + high open" value={d.findings.open_by_severity.critical + d.findings.open_by_severity.high} to={findingsLink('severity=high')} />
            <Tile label="Projects" value={d.projects} to="/projects" />
            <Tile label="Discovery scans" value={d.scans} />
            <Tile label="Reopened (regressions)" value={d.findings.reopened} to={findingsLink('status=reopened')} />
            <Tile label="Verified fixes" value={d.findings.verified} to={findingsLink('status=verified&open_only=false')} />
          </div>
          <p className="text-xs text-slate-500">Counts come straight from stored scans and executions. They describe what was tested, not overall application quality.
            {d.avg_duration_ms != null && ` Average test duration ${(d.avg_duration_ms / 1000).toFixed(1)}s.`}</p>

          <div className="grid gap-4 md:grid-cols-3">
            <div className="md:col-span-2"><Card title={`Executions, last ${d.scope.days} days`}><Trend days={d.trend} /></Card></div>
            <Card title="Open findings by severity">
              <ul className="space-y-1 text-sm">
                {Object.entries(d.findings.open_by_severity).map(([s, n]) => (
                  <li key={s} className="flex justify-between"><Link className="hover:underline" to={findingsLink(`severity=${s}`)}><Badge>{s}</Badge></Link><span>{n}</span></li>
                ))}
              </ul>
            </Card>
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Card title="Recent scans">
              {d.recent_scans.length === 0 && <Empty>No scans yet.</Empty>}
              <ul className="divide-y divide-slate-100 text-sm">
                {d.recent_scans.map((s) => (
                  <li key={s.id} className="flex justify-between py-1.5">
                    <Link className="text-indigo-700 hover:underline" to={`/scans/${s.id}`}>{fmt(s.created_at)}</Link>
                    <span className="text-xs text-slate-500">{s.pages ?? 0} pages</span><Badge>{s.status}</Badge>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Recent findings">
              {d.recent_findings.length === 0 && <Empty>No findings yet.</Empty>}
              <ul className="divide-y divide-slate-100 text-sm">
                {d.recent_findings.map((f) => (
                  <li key={f.id} className="py-1.5">
                    <Link className="text-indigo-700 hover:underline" to={`/findings/${f.id}`}>{f.title}</Link>
                    <div className="flex gap-1"><Badge>{f.severity}</Badge><Badge>{f.status}</Badge></div>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Mixed recent results">
              <p className="mb-2 text-xs text-slate-500">Tests that both passed and failed in their last 10 runs. Possibly flaky, or a defect that was fixed or newly introduced.</p>
              {d.mixed_results.length === 0 && <Empty>None.</Empty>}
              <ul className="text-sm">{d.mixed_results.map((m) => <li key={m.test_case_id}><span className="font-mono text-xs">{m.key}</span> {m.title} <span className="text-xs text-slate-500">({m.passed}✓ {m.failed}✗)</span></li>)}</ul>
            </Card>
          </div>
        </>
      )}
    </>
  )
}
