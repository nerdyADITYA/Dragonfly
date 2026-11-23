import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, fmt, inputCls } from '../ui.jsx'

export const STATUSES = ['new', 'triaged', 'assigned', 'in_progress', 'fixed', 'ready_for_retest', 'verified',
  'reopened', 'wont_fix', 'duplicate', 'false_positive']
export const SEVERITIES = ['critical', 'high', 'medium', 'low', 'info']

export function FindingsCard({ projectId }) {
  const [filter, setFilter] = useState({ status: '', severity: '', open_only: true })
  const qs = new URLSearchParams(Object.entries(filter).filter(([, v]) => v)).toString()
  const findings = useQuery({ queryKey: ['findings', projectId, qs], queryFn: () => api(`/projects/${projectId}/findings?${qs}`) })
  const sel = 'rounded border border-slate-300 px-2 py-1 text-sm'
  return (
    <Card title="Findings" actions={
      <>
        <label className="flex items-center gap-1 text-sm"><input type="checkbox" checked={filter.open_only} onChange={(e) => setFilter({ ...filter, open_only: e.target.checked })} /> open only</label>
        <select aria-label="Status filter" className={sel} value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value })}>
          <option value="">any status</option>{STATUSES.map((s) => <option key={s}>{s}</option>)}
        </select>
        <select aria-label="Severity filter" className={sel} value={filter.severity} onChange={(e) => setFilter({ ...filter, severity: e.target.value })}>
          <option value="">any severity</option>{SEVERITIES.map((s) => <option key={s}>{s}</option>)}
        </select>
      </>
    }>
      <ErrorBox error={findings.error} />
      {findings.data?.length === 0 && <Empty>No findings match. Findings appear when an approved test fails with evidence.</Empty>}
      <ul className="divide-y divide-slate-100">
        {findings.data?.map((f) => (
          <li key={f.id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
            <Link className="flex-1 font-medium text-indigo-700 hover:underline" to={`/findings/${f.id}`}>{f.title}</Link>
            <Badge>{f.severity}</Badge><Badge>{f.confidence}</Badge><Badge>{f.status}</Badge>
            <span className="text-xs text-slate-500">×{f.occurrences} · last {fmt(f.last_detected_at)}</span>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function TicketsCard({ projectId }) {
  const tickets = useQuery({ queryKey: ['tickets', projectId], queryFn: () => api(`/projects/${projectId}/tickets`) })
  return (
    <Card title="Tickets">
      {tickets.data?.length === 0 && <Empty>No tickets yet. Create one from a finding.</Empty>}
      <ul className="divide-y divide-slate-100 text-sm">
        {tickets.data?.map((t) => (
          <li key={t.id} className="flex flex-wrap items-center gap-2 py-2">
            <span className="font-mono text-xs text-slate-500">TP-{t.number}</span>
            <Link className="flex-1 text-indigo-700 hover:underline" to={`/findings/${t.finding_id}`}>{t.title}</Link>
            <span className="text-xs text-slate-500">{t.assignee?.name || 'unassigned'}</span>
            <Badge>{t.severity}</Badge><Badge>{t.status}</Badge>
          </li>
        ))}
      </ul>
    </Card>
  )
}

export function DevelopersCard({ projectId }) {
  const qc = useQueryClient()
  const devs = useQuery({ queryKey: ['devs', projectId], queryFn: () => api(`/projects/${projectId}/developers`) })
  const [f, setF] = useState({ name: '', email: '', team: '' })
  const refresh = () => qc.invalidateQueries({ queryKey: ['devs', projectId] })
  const add = useMutation({ mutationFn: () => api(`/projects/${projectId}/developers`, { method: 'POST', body: f }),
    onSuccess: () => { setF({ name: '', email: '', team: '' }); refresh() } })
  const del = useMutation({ mutationFn: (id) => api(`/developers/${id}`, { method: 'DELETE' }), onSuccess: refresh })
  return (
    <Card title="Developers (assignees)">
      <ul className="mb-3 divide-y divide-slate-100 text-sm">
        {devs.data?.length === 0 && <Empty>Add the people tickets can be assigned to.</Empty>}
        {devs.data?.map((d) => (
          <li key={d.id} className="flex items-center justify-between py-1.5">
            <span>{d.name} <span className="text-xs text-slate-500">{d.email}{d.team && ` · ${d.team}`}</span></span>
            <button className="text-xs text-red-700 hover:underline" onClick={() => del.mutate(d.id)}>Remove</button>
          </li>
        ))}
      </ul>
      <form className="flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <input aria-label="Name" required placeholder="Name" className={`${inputCls} mt-0 w-36 flex-1`} value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} />
        <input aria-label="Email" placeholder="Email" type="email" className={`${inputCls} mt-0 w-44 flex-1`} value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} />
        <input aria-label="Team" placeholder="Team" className={`${inputCls} mt-0 w-28`} value={f.team} onChange={(e) => setF({ ...f, team: e.target.value })} />
        <Button disabled={add.isPending}>Add</Button>
      </form>
      <ErrorBox error={add.error || del.error} />
    </Card>
  )
}
