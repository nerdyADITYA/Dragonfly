import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ACTIVE, api } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Field, Loading, fmt, inputCls } from '../ui.jsx'
import { DevelopersCard, FindingsCard, TicketsCard } from './Findings.jsx'
import TestCases from './TestCases.jsx'

function EnvironmentForm({ projectId }) {
  const qc = useQueryClient()
  const [f, setF] = useState({ name: 'staging', base_url: '', environment_type: 'staging', allowed_domains: '',
    excluded_paths: '', allow_private_network: false, max_pages: 25, max_depth: 3, authorization_confirmed: false })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const list = (s) => s.split(',').map((x) => x.trim()).filter(Boolean)
  const create = useMutation({
    mutationFn: () => api(`/projects/${projectId}/environments`, { method: 'POST', body: {
      name: f.name, base_url: f.base_url, environment_type: f.environment_type, authorization_confirmed: f.authorization_confirmed,
      scan_policy: { allowed_domains: list(f.allowed_domains), excluded_paths: list(f.excluded_paths),
        allow_private_network: f.allow_private_network, max_pages: +f.max_pages, max_depth: +f.max_depth },
    } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['envs', projectId] }),
  })
  return (
    <form className="grid gap-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
      <Field label="Name"><input className={inputCls} required value={f.name} onChange={set('name')} /></Field>
      <Field label="Type">
        <select className={inputCls} value={f.environment_type} onChange={set('environment_type')}>
          {['local', 'development', 'qa', 'staging', 'production'].map((t) => <option key={t}>{t}</option>)}
        </select>
      </Field>
      <Field label="Base URL" hint="Demo app in Docker: http://demo-app:8001/">
        <input className={inputCls} required type="url" placeholder="https://staging.example.com/" value={f.base_url} onChange={set('base_url')} />
      </Field>
      <Field label="Allowed domains" hint="Comma separated; empty = base URL host only; *.x.com for subdomains">
        <input className={inputCls} value={f.allowed_domains} onChange={set('allowed_domains')} />
      </Field>
      <Field label="Excluded paths" hint="Comma separated prefixes, e.g. /admin, /billing">
        <input className={inputCls} value={f.excluded_paths} onChange={set('excluded_paths')} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Max pages"><input className={inputCls} type="number" min="1" max="500" value={f.max_pages} onChange={set('max_pages')} /></Field>
        <Field label="Max depth"><input className={inputCls} type="number" min="0" max="10" value={f.max_depth} onChange={set('max_depth')} /></Field>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={f.allow_private_network} onChange={set('allow_private_network')} />
        <span>Target is on a private/local network (needed for localhost or Docker demo apps)</span>
      </label>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" className="mt-1" checked={f.authorization_confirmed} onChange={set('authorization_confirmed')} />
        <span><strong>I am authorized to test this application.</strong> Scans are blocked until this is confirmed.</span>
      </label>
      <div className="md:col-span-2"><ErrorBox error={create.error} /></div>
      <div><Button disabled={create.isPending}>Add environment</Button></div>
    </form>
  )
}

function ScanConfirm({ env, projectId, onClose }) {
  const nav = useNavigate()
  const p = env.scan_policy
  const start = useMutation({
    mutationFn: () => api(`/projects/${projectId}/discovery`, { method: 'POST', body: { environment_id: env.id } }),
    onSuccess: (scan) => nav(`/scans/${scan.id}`),
  })
  return (
    <div className="mt-3 rounded border border-indigo-200 bg-indigo-50 p-3 text-sm">
      <p className="font-medium">Confirm discovery scan</p>
      <ul className="mt-1 list-disc pl-5 text-slate-700">
        <li>Target: {env.base_url}</li>
        <li>Allowed hosts: {p.allowed_domains.length ? p.allowed_domains.join(', ') : new URL(env.base_url).host + ' (base URL host)'}</li>
        <li>Excluded paths: {p.excluded_paths.join(', ') || 'none'}</li>
        <li>Limits: {p.max_pages} pages, depth {p.max_depth}, {p.max_duration_seconds}s</li>
        <li>Safety: follows links only; never submits forms; skips destructive-looking links; destructive actions {p.destructive_actions_allowed ? 'ALLOWED' : 'blocked'}</li>
      </ul>
      <ErrorBox error={start.error} />
      <div className="mt-2 flex gap-2">
        <Button onClick={() => start.mutate()} disabled={start.isPending}>Start scan</Button>
        <Button variant="secondary" onClick={onClose}>Cancel</Button>
      </div>
    </div>
  )
}

export default function Project() {
  const { id } = useParams()
  const [confirming, setConfirming] = useState(null)
  const [showEnvForm, setShowEnvForm] = useState(false)
  const project = useQuery({ queryKey: ['project', id], queryFn: () => api(`/projects/${id}`) })
  const envs = useQuery({ queryKey: ['envs', id], queryFn: () => api(`/projects/${id}/environments`) })
  const scans = useQuery({ queryKey: ['scans', id], queryFn: () => api(`/projects/${id}/scans`),
    refetchInterval: (q) => (q.state.data?.some((s) => ACTIVE.has(s.status)) ? 2000 : false) })
  const runs = useQuery({ queryKey: ['runs', id], queryFn: () => api(`/projects/${id}/test-runs`),
    refetchInterval: (q) => (q.state.data?.some((s) => ACTIVE.has(s.status)) ? 2000 : false) })

  if (project.isLoading) return <Loading />
  if (project.error) return <ErrorBox error={project.error} />

  return (
    <>
      <div>
        <h1 className="text-2xl font-bold">{project.data.name}</h1>
        <p className="text-sm text-slate-500">{project.data.description}</p>
      </div>

      <Card title="Environments" actions={<Button variant="secondary" onClick={() => setShowEnvForm(!showEnvForm)}>{showEnvForm ? 'Close' : 'Add environment'}</Button>}>
        {showEnvForm && <div className="mb-4 border-b border-slate-100 pb-4"><EnvironmentForm projectId={id} /></div>}
        {envs.data?.length === 0 && !showEnvForm && <Empty>Add an environment (target URL + scope) before scanning.</Empty>}
        <ul className="divide-y divide-slate-100">
          {envs.data?.map((e) => (
            <li key={e.id} className="py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-medium">{e.name}</span> <Badge>{e.environment_type}</Badge>{' '}
                  {!e.authorization_confirmed && <Badge>authorization not confirmed</Badge>}
                  <p className="text-xs text-slate-500">{e.base_url}</p>
                </div>
                <Button disabled={!e.authorization_confirmed} onClick={() => setConfirming(e.id)}>Discover</Button>
              </div>
              {confirming === e.id && <ScanConfirm env={e} projectId={id} onClose={() => setConfirming(null)} />}
            </li>
          ))}
        </ul>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Discovery scans">
          {scans.data?.length === 0 && <Empty>No scans yet.</Empty>}
          <ul className="divide-y divide-slate-100 text-sm">
            {scans.data?.map((s) => (
              <li key={s.id} className="flex items-center justify-between py-2">
                <Link className="text-indigo-700 hover:underline" to={`/scans/${s.id}`}>{fmt(s.created_at)}</Link>
                <span className="text-xs text-slate-500">{s.summary_json?.pages ?? 0} pages</span>
                <Badge>{s.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Test runs">
          {runs.data?.length === 0 && <Empty>No test runs yet. Approve tests, then run them.</Empty>}
          <ul className="divide-y divide-slate-100 text-sm">
            {runs.data?.map((r) => (
              <li key={r.id} className="flex items-center justify-between py-2">
                <Link className="text-indigo-700 hover:underline" to={`/runs/${r.id}`}>{fmt(r.created_at)}</Link>
                <span className="text-xs text-slate-500">
                  {Object.entries(r.summary_json?.counts || {}).map(([k, v]) => `${v} ${k}`).join(' · ')}
                </span>
                <Badge>{r.status}</Badge>
              </li>
            ))}
          </ul>
        </Card>
      </div>

      <FindingsCard projectId={id} />
      <div className="grid gap-4 md:grid-cols-2">
        <TicketsCard projectId={id} />
        <DevelopersCard projectId={id} />
      </div>

      <TestCases projectId={id} envs={envs.data || []} scans={scans.data || []} />
    </>
  )
}
