import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ACTIVE, api, artifactUrl, pollWhileActive, useLiveEvents } from '../api.js'
import AppMap from './AppMap.jsx'
import { Badge, Button, Card, Empty, ErrorBox, Loading, fmt } from '../ui.jsx'

function PageRow({ p }) {
  const [open, setOpen] = useState(false)
  return (
    <li className="py-2">
      <button className="flex w-full items-center gap-3 text-left text-sm" onClick={() => setOpen(!open)}>
        <span className="w-6 text-xs text-slate-400">d{p.depth}</span>
        <span className="flex-1"><span className="font-medium">{p.title || '(untitled)'}</span> <span className="text-xs text-slate-500">{p.url}</span></span>
        <span className="text-xs text-slate-500">{p.elements.length} elements · {p.forms.length} forms</span>
        {p.status_code && <Badge>{String(p.status_code)}</Badge>}
      </button>
      {open && (
        <div className="mt-2 grid gap-3 rounded bg-slate-50 p-3 md:grid-cols-2">
          {p.screenshot_artifact_id && (
            <a href={artifactUrl(p.screenshot_artifact_id)} target="_blank" rel="noreferrer">
              <img src={artifactUrl(p.screenshot_artifact_id)} alt={`Screenshot of ${p.url}`} className="max-h-80 rounded border object-top" />
            </a>
          )}
          <div className="space-y-2 text-xs">
            {p.forms.map((f) => (
              <div key={f.id}>
                <p className="font-semibold">Form “{f.name}” ({f.method.toUpperCase()}) → submit “{f.submit_label}”</p>
                <ul className="pl-4">{f.fields_json.map((fl) => <li key={fl.name}>{fl.label || fl.name} <span className="text-slate-500">[{fl.type}{fl.required ? ', required' : ''}]</span></li>)}</ul>
              </div>
            ))}
            <p className="font-semibold">Elements</p>
            <ul className="max-h-48 overflow-auto pl-4">
              {p.elements.map((e) => <li key={e.id}><span className="text-slate-500">{e.element_type}</span> {e.accessible_name || '—'}</li>)}
            </ul>
          </div>
        </div>
      )}
    </li>
  )
}

export default function Scan() {
  const { id } = useParams()
  const qc = useQueryClient()
  const scan = useQuery({ queryKey: ['scan', id], queryFn: () => api(`/discovery/${id}`), refetchInterval: pollWhileActive })
  const active = ACTIVE.has(scan.data?.status)
  const pages = useQuery({ queryKey: ['pages', id], queryFn: () => api(`/discovery/${id}/pages`), refetchInterval: active ? 5000 : false })
  const logs = useQuery({ queryKey: ['scanlogs', id], queryFn: () => api(`/discovery/${id}/logs`), refetchInterval: active ? 5000 : false })
  const stop = useMutation({ mutationFn: () => api(`/discovery/${id}/stop`, { method: 'POST' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['scan', id] }) })
  const live = useLiveEvents(scan.data?.project_id)

  if (scan.isLoading) return <Loading />
  if (scan.error) return <ErrorBox error={scan.error} />
  const s = scan.data
  const sum = s.summary_json || {}
  const report = `/api/v1/scan-runs/${id}/report`
  return (
    <>
      <Link to={`/projects/${s.project_id}`} className="text-sm text-indigo-700">← Project</Link>
      <Card title={<>Discovery scan <Badge>{s.status}</Badge></>} actions={active
        ? <Button variant="danger" onClick={() => stop.mutate()}>Stop scan</Button>
        : <>
            <a className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50" href={report} target="_blank" rel="noreferrer">View report</a>
            <a className="rounded border border-slate-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-slate-50" href={`${report}?download=true`}>Download HTML</a>
          </>}>
        {active && live?.scan_id === id && live.type === 'discovery.page_found' && (
          <p className="mb-2 text-sm text-blue-800" role="status">Exploring… last found <span className="font-mono">{live.url}</span> ({live.pages} pages so far)</p>
        )}
        <dl className="grid grid-cols-2 gap-2 text-sm md:grid-cols-6">
          <div><dt className="text-slate-500">Stage</dt><dd>{s.stage}</dd></div>
          <div><dt className="text-slate-500">Pages</dt><dd>{pages.data?.length ?? 0}</dd></div>
          <div><dt className="text-slate-500">Forms</dt><dd>{pages.data?.reduce((n, p) => n + p.forms.length, 0) ?? 0}</dd></div>
          <div><dt className="text-slate-500">Skipped (unsafe)</dt><dd>{sum.skipped_destructive ?? '—'}</dd></div>
          <div><dt className="text-slate-500">Blocked (scope)</dt><dd>{sum.skipped_out_of_scope ?? '—'}</dd></div>
          <div><dt className="text-slate-500">Stopped because</dt><dd>{sum.stopped_reason ?? '—'}</dd></div>
        </dl>
        <p className="mt-2 text-xs text-slate-500">Started {fmt(s.started_at)} · finished {fmt(s.completed_at)}</p>
        {s.error_message && <ErrorBox error={s.error_message} />}
        {sum.limitations && <ul className="mt-2 list-disc pl-5 text-xs text-slate-500">{sum.limitations.map((l) => <li key={l}>{l}</li>)}</ul>}
      </Card>

      {pages.data?.length > 0 && <AppMap scanId={id} />}

      <Card title="Discovered pages">
        {pages.data?.length === 0 && <Empty>{active ? 'Exploring…' : 'No pages discovered.'}</Empty>}
        <ul className="divide-y divide-slate-100">{pages.data?.map((p) => <PageRow key={p.id} p={p} />)}</ul>
      </Card>

      {sum.skipped?.length > 0 && (
        <Card title="Skipped / blocked links">
          <ul className="text-xs">{sum.skipped.map((k, i) => <li key={i}><span className="font-mono">{k.url}</span> — {k.reason}</li>)}</ul>
        </Card>
      )}

      <Card title="Scan log">
        {logs.data?.length === 0 && <Empty>No log entries.</Empty>}
        <ul className="font-mono text-xs">{logs.data?.map((l, i) => <li key={i} className={l.severity === 'error' ? 'text-red-700' : l.severity === 'warning' ? 'text-orange-700' : ''}>{fmt(l.created_at)} [{l.severity}] {l.message}</li>)}</ul>
      </Card>
    </>
  )
}
