import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ACTIVE, api, artifactUrl, useLiveEvents } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Field, Loading, fmt, inputCls } from '../ui.jsx'
import { HttpExchange } from './Execution.jsx'
import { SEVERITIES, STATUSES } from './Findings.jsx'

const MANUAL = STATUSES.filter((s) => !['verified', 'duplicate'].includes(s))

function Shot({ id, label }) {
  if (!id) return null
  return (
    <figure>
      <figcaption className="mb-1 text-xs font-medium text-slate-600">{label}</figcaption>
      <a href={artifactUrl(id)} target="_blank" rel="noreferrer">
        <img src={artifactUrl(id)} alt={label} className="max-h-72 rounded border" />
      </a>
    </figure>
  )
}

function Triage({ f }) {
  const qc = useQueryClient()
  const [status, setStatus] = useState(f.status)
  const [severity, setSeverity] = useState(f.severity)
  const [reason, setReason] = useState('')
  const save = useMutation({
    mutationFn: () => api(`/findings/${f.id}`, { method: 'PATCH', body: { status: status !== f.status ? status : null, severity: severity !== f.severity ? severity : null, reason } }),
    onSuccess: () => { setReason(''); qc.invalidateQueries({ queryKey: ['finding', f.id] }) },
  })
  const dup = useMutation({
    mutationFn: (id) => api(`/findings/${f.id}/duplicate`, { method: 'POST', body: { duplicate_of_id: id } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['finding', f.id] }),
  })
  const changed = status !== f.status || severity !== f.severity
  return (
    <Card title="Triage">
      <div className="space-y-3">
        <Field label="Status" hint="“verified” is set only by a passing retest.">
          <select className={inputCls} value={status} onChange={(e) => setStatus(e.target.value)}>
            {[...new Set([f.status, ...MANUAL])].map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <Field label="Severity">
          <select className={inputCls} value={severity} onChange={(e) => setSeverity(e.target.value)}>{SEVERITIES.map((s) => <option key={s}>{s}</option>)}</select>
        </Field>
        <Field label={severity !== f.severity ? 'Reason (required for severity override)' : 'Note (optional)'}>
          <input className={inputCls} value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        <ErrorBox error={save.error} />
        <Button disabled={!changed || save.isPending} onClick={() => save.mutate()}>Save</Button>
        {f.duplicate_candidates.length > 0 && (
          <div className="border-t border-slate-100 pt-3 text-sm">
            <p className="font-medium">Possible duplicates <span className="text-xs font-normal text-slate-500">(same page &amp; category — suggestion only)</span></p>
            <ul>{f.duplicate_candidates.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 py-1">
                <Link className="text-indigo-700 hover:underline" to={`/findings/${d.id}`}>{d.title}</Link>
                <button className="text-xs text-slate-600 hover:underline" onClick={() => dup.mutate(d.id)}>Mark this as duplicate of it</button>
              </li>
            ))}</ul>
            <ErrorBox error={dup.error} />
          </div>
        )}
      </div>
    </Card>
  )
}

function TicketPanel({ f }) {
  const qc = useQueryClient()
  const devs = useQuery({ queryKey: ['devs', f.project_id], queryFn: () => api(`/projects/${f.project_id}/developers`) })
  const [dev, setDev] = useState('')
  const [showReport, setShowReport] = useState(false)
  const refresh = () => qc.invalidateQueries({ queryKey: ['finding', f.id] })
  const create = useMutation({ mutationFn: () => api(`/findings/${f.id}/ticket`, { method: 'POST', body: { assignee_id: dev || null } }), onSuccess: refresh })
  const assign = useMutation({ mutationFn: () => api(`/tickets/${f.ticket.id}/assign`, { method: 'POST', body: { developer_id: dev } }), onSuccess: refresh })
  const t = f.ticket
  const devSelect = (
    <select aria-label="Assignee" className={inputCls} value={dev} onChange={(e) => setDev(e.target.value)}>
      <option value="">{t ? 'Choose developer…' : 'Unassigned'}</option>
      {devs.data?.map((d) => <option key={d.id} value={d.id}>{d.name}{d.team && ` (${d.team})`}</option>)}
    </select>
  )
  return (
    <Card title={t ? <>Ticket <span className="font-mono">TP-{t.number}</span></> : 'Ticket'}>
      {!t ? (
        <div className="space-y-2">
          {devs.data?.length === 0 && <p className="text-xs text-slate-500">Add developers on the project page to assign tickets.</p>}
          {devSelect}
          <Button disabled={create.isPending || ['duplicate', 'false_positive'].includes(f.status)} onClick={() => create.mutate()}>Create ticket</Button>
          <ErrorBox error={create.error} />
        </div>
      ) : (
        <div className="space-y-2 text-sm">
          <p>Assignee: <strong>{t.assignee?.name || 'unassigned'}</strong> · status <Badge>{t.status}</Badge></p>
          <div className="flex gap-2">{devSelect}<Button variant="secondary" disabled={!dev || assign.isPending} onClick={() => assign.mutate()}>Assign</Button></div>
          <ErrorBox error={assign.error} />
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => setShowReport(!showReport)}>{showReport ? 'Hide' : 'Show'} bug report</Button>
            <Button variant="secondary" onClick={() => navigator.clipboard?.writeText(`# ${t.title}\n\n${t.description}`)}>Copy as Markdown</Button>
          </div>
          {showReport && <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-slate-50 p-2 text-xs">{t.description}</pre>}
        </div>
      )}
    </Card>
  )
}

function RetestPanel({ f }) {
  const qc = useQueryClient()
  const [related, setRelated] = useState(false)
  const start = useMutation({ mutationFn: () => api(`/findings/${f.id}/retest`, { method: 'POST', body: { include_related: related } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['finding', f.id] }) })
  const closed = ['verified', 'duplicate', 'false_positive', 'wont_fix'].includes(f.status)
  return (
    <Card title="Retest">
      <p className="mb-2 text-xs text-slate-500">Replays the exact test version that detected this defect in a fresh browser. Pass → verified; same failure → reopened; anything else needs review.</p>
      {!closed && (
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <Button disabled={start.isPending} onClick={() => start.mutate()}>Retest now</Button>
          <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={related} onChange={(e) => setRelated(e.target.checked)} /> also re-run approved tests on the same page</label>
        </div>
      )}
      <ErrorBox error={start.error} />
      {f.retest_runs.length === 0 ? <Empty>No retests yet.</Empty> : (
        <ul className="divide-y divide-slate-100 text-sm">
          {f.retest_runs.map((r) => {
            const ex = r.executions.find((e) => e.test_case_id === f.test_case_id)
            return (
              <li key={r.id} className="flex items-center justify-between py-1.5">
                <Link className="text-indigo-700 hover:underline" to={ex ? `/executions/${ex.id}` : `/runs/${r.id}`}>{fmt(r.created_at)}</Link>
                <span className="text-xs text-slate-500">{r.executions.length} test(s)</span>
                <Badge>{ex?.status || r.status}</Badge>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

function History({ f }) {
  const qc = useQueryClient()
  const [body, setBody] = useState('')
  const add = useMutation({ mutationFn: () => api(`/findings/${f.id}/comments`, { method: 'POST', body: { body } }),
    onSuccess: () => { setBody(''); qc.invalidateQueries({ queryKey: ['finding', f.id] }) } })
  return (
    <Card title="History">
      <ol className="space-y-1.5 text-sm">
        {f.events.map((e, i) => (
          <li key={i} className={e.event_type === 'comment' ? 'rounded bg-slate-50 p-2' : ''}>
            <span className="text-xs text-slate-500">{fmt(e.created_at)} · {e.actor} · {e.event_type}</span><br />{e.message}
          </li>
        ))}
      </ol>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <input aria-label="Comment" required className={`${inputCls} mt-0 flex-1`} placeholder="Add a comment" value={body} onChange={(e) => setBody(e.target.value)} />
        <Button disabled={add.isPending}>Comment</Button>
      </form>
      <ErrorBox error={add.error} />
    </Card>
  )
}

export default function Finding() {
  const { id } = useParams()
  const q = useQuery({ queryKey: ['finding', id], queryFn: () => api(`/findings/${id}`),
    refetchInterval: (q) => (q.state.data?.retest_runs.some((r) => ACTIVE.has(r.status)) ? 5000 : false) })
  useLiveEvents(q.data?.project_id)
  if (q.isLoading) return <Loading />
  if (q.error) return <ErrorBox error={q.error} />
  const f = q.data
  const a = f.ai_analysis_json || {}
  return (
    <>
      <Link to={`/projects/${f.project_id}`} className="text-sm text-indigo-700">← Project</Link>
      <Card title={<>{f.title} <Badge>{f.status}</Badge></>}>
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge>{f.severity}</Badge><Badge>{f.confidence}</Badge><Badge>{f.category}</Badge>
          <span className="text-xs text-slate-500">seen {f.occurrences}× · first {fmt(f.first_detected_at)} · last {fmt(f.last_detected_at)} · {f.page_url}</span>
        </div>
        {f.duplicate_of_id && <p className="mt-2 text-sm">Duplicate of <Link className="text-indigo-700" to={`/findings/${f.duplicate_of_id}`}>another finding</Link>.</p>}
        {f.description && <p className="mt-2 text-sm">{f.description}</p>}
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-4 md:col-span-2">
          <Card title="What happened">
            <div className="grid gap-3 text-sm md:grid-cols-2">
              <div><p className="font-medium">Expected</p><p>{f.expected_result || '—'}</p></div>
              <div><p className="font-medium">Actual</p><p className="text-red-800">{f.actual_result || '—'}</p></div>
            </div>
            <p className="mt-3 text-sm font-medium">Steps to reproduce</p>
            <ol className="list-decimal pl-5 text-sm">{f.reproduction_steps_json.map((s, i) => <li key={i}>{s}</li>)}</ol>
          </Card>

          <Card title="Evidence">
            <div className="grid gap-3 md:grid-cols-2">
              <Shot id={f.original_screenshot_id} label="At first detection" />
              {f.http_evidence && <div className="md:col-span-2"><p className="text-xs font-medium text-slate-600">HTTP response at failure (sanitized)</p><HttpExchange ev={f.http_evidence} /></div>}
              {f.latest_screenshot_id !== f.original_screenshot_id && <Shot id={f.latest_screenshot_id} label="Most recent failure" />}
            </div>
            <p className="mt-2 text-sm">
              <Link className="text-indigo-700 hover:underline" to={`/executions/${f.test_execution_id}`}>Original execution</Link> (all steps, trace, console &amp; network)
              {f.last_execution_id !== f.test_execution_id && <> · <Link className="text-indigo-700 hover:underline" to={`/executions/${f.last_execution_id}`}>latest failing execution</Link></>}
            </p>
          </Card>

          <Card title={<>AI analysis <span className="text-xs font-normal text-amber-700">hypothesis — not a proven root cause</span></>}>
            <div className="space-y-2 text-sm">
              <p>{a.summary}</p>
              {a.likely_cause && <p><span className="font-medium">Likely cause:</span> {a.likely_cause}</p>}
              {a.affected_component && <p><span className="font-medium">Affected:</span> {a.affected_component}</p>}
              {a.evidence?.length > 0 && <><p className="font-medium">Based on</p><ul className="list-disc pl-5">{a.evidence.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
              {a.suggested_investigation?.length > 0 && <><p className="font-medium">Investigate</p><ul className="list-disc pl-5">{a.suggested_investigation.map((x, i) => <li key={i}>{x}</li>)}</ul></>}
              {a.suggested_fix_direction && <p><span className="font-medium">Fix direction:</span> {a.suggested_fix_direction}</p>}
              <p className="text-xs text-slate-500">by {a.provider}{a.confidence && ` · model confidence ${a.confidence}`}{a.note && ` · ${a.note}`}{a.error && ` · ${a.error}`}</p>
            </div>
          </Card>

          <History f={f} />
        </div>
        <div className="space-y-4">
          <Triage key={`${f.status}-${f.severity}`} f={f} />
          <TicketPanel f={f} />
          <RetestPanel f={f} />
        </div>
      </div>
    </>
  )
}
