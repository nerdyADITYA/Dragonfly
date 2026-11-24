import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Field, inputCls } from '../ui.jsx'
import TestEditor from './TestEditor.jsx'

// Plain-language rendering of an action, so non-automation users can review tests (§36).
export function describeStep(a) {
  const tg = a.target || {}
  const t = tg.role && tg.name ? `the “${tg.name}” ${tg.role}`
    : Object.entries(tg).filter(([, v]) => v).map(([k, v]) => `${k} “${v}”`).join(', ')
  const say = {
    navigate: `Open ${a.url}`, click: `Click ${t}`, fill: `Type “${a.value}” into ${t}`, select: `Choose “${a.value}” in ${t}`,
    check: `Tick ${t}`, uncheck: `Untick ${t}`, press: `Press ${a.key}${t ? ` on ${t}` : ''}`, hover: `Hover ${t}`,
    wait_for: `Wait for ${t}`, screenshot: 'Take a screenshot',
    assert_text: `Check text “${a.text}” is shown${t ? ` in ${t}` : ''}`, assert_visible: `Check ${t} is visible`,
    assert_hidden: `Check ${t} is hidden`, assert_url: `Check URL contains “${a.value}”`,
    assert_title: `Check title contains “${a.value}”`, assert_value: `Check ${t} has value “${a.value}”`,
    assert_count: `Check there are ${a.count} of ${t}`,
  }
  return say[a.type] || a.type
}

function Versions({ tcId }) {
  const vs = useQuery({ queryKey: ['versions', tcId], queryFn: () => api(`/test-cases/${tcId}/versions`) })
  const [shown, setShown] = useState(null)
  return (
    <div className="rounded border border-slate-200 bg-white p-2 text-xs">
      <p className="font-medium">Version history</p>
      {vs.data?.length === 0 && <p className="text-slate-500">No recorded versions (created before versioning).</p>}
      <ul>{vs.data?.map((v) => (
        <li key={v.version}>
          <button className="text-indigo-700 hover:underline" onClick={() => setShown(shown === v.version ? null : v.version)}>v{v.version}</button>{' '}
          {v.source} · {v.created_by} · {new Date(v.created_at).toLocaleString()}
          {shown === v.version && <ol className="ml-4 list-decimal">{v.definition_json.steps.map((s, i) => <li key={i}>{describeStep(s)}</li>)}</ol>}
        </li>
      ))}</ul>
    </div>
  )
}

function TestRow({ tc, selected, onSelect, envId }) {
  const qc = useQueryClient()
  const nav = useNavigate()
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const [regen, setRegen] = useState(null)
  const [showVersions, setShowVersions] = useState(false)
  const d = tc.definition_json
  const refresh = () => { qc.invalidateQueries({ queryKey: ['tests', tc.project_id] }); qc.invalidateQueries({ queryKey: ['versions', tc.id] }) }
  const act = useMutation({ mutationFn: (verb) => api(`/test-cases/${tc.id}/${verb}`, { method: 'POST' }), onSuccess: refresh })
  const save = useMutation({
    mutationFn: (definition) => api(`/test-cases/${tc.id}`, { method: 'PATCH', body: { definition } }),
    onSuccess: () => { setEditing(false); refresh() },
  })
  const regenerate = useMutation({
    mutationFn: () => api(`/test-cases/${tc.id}/regenerate`, { method: 'POST', body: { instructions: regen } }),
    onSuccess: () => { setRegen(null); refresh() },
  })
  const runOne = useMutation({
    mutationFn: () => api('/test-runs', { method: 'POST', body: { environment_id: envId, test_case_ids: [tc.id] } }),
    onSuccess: (r) => nav(`/runs/${r.id}`),
  })
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2">
        <input type="checkbox" aria-label={`Select ${tc.title}`} disabled={tc.status !== 'approved'} checked={selected} onChange={onSelect} />
        <button className="flex-1 text-left text-sm" onClick={() => setOpen(!open)}>
          <span className="font-mono text-xs text-slate-500">{tc.key}</span> <span className="font-medium">{tc.title}</span>
        </button>
        <Badge>{tc.category}</Badge><Badge>{tc.priority}</Badge>
        {d.side_effect !== 'none' && <Badge>{d.side_effect.replace('_', ' ')}</Badge>}
        <Badge>{tc.status}</Badge>
      </div>
      {open && (
        <div className="mt-2 ml-6 space-y-2 rounded bg-slate-50 p-3 text-sm">
          {d.description && <p>{d.description}</p>}
          <ol className="list-decimal pl-5">{d.steps.map((s, i) => <li key={i} className={s.type.startsWith('assert') ? 'text-indigo-800' : ''}>{describeStep(s)}</li>)}</ol>
          {d.expected_outcomes.length > 0 && <p><span className="font-medium">Expected:</span> {d.expected_outcomes.join('; ')}</p>}
          {d.data_requirements.length > 0 && <p><span className="font-medium">Needs data:</span> {d.data_requirements.join('; ')}</p>}
          <p className="text-xs text-slate-500">Why generated: {d.source_observations.join('; ') || '—'} · by {tc.generated_by} · confidence {d.confidence} · v{tc.version}</p>
          {tc.validation_errors_json.length > 0 && (
            <ul className="rounded bg-orange-50 p-2 text-xs text-orange-800">{tc.validation_errors_json.map((e) => <li key={e}>⚠ {e}</li>)}</ul>
          )}
          {editing ? (
            <>
              <TestEditor definition={d} saving={save.isPending} onSave={(def) => save.mutate(def)} onCancel={() => setEditing(false)} />
              <ErrorBox error={save.error} />
            </>
          ) : (
            <div className="flex flex-wrap gap-2">
              {tc.status === 'approved' && <Button disabled={!envId || runOne.isPending} onClick={() => runOne.mutate()}>Run</Button>}
              {['draft', 'disabled', 'rejected'].includes(tc.status) && <Button onClick={() => act.mutate('approve')}>Approve</Button>}
              {['draft', 'approved', 'blocked'].includes(tc.status) && <Button variant="danger" onClick={() => act.mutate('reject')}>Reject</Button>}
              {['draft', 'approved'].includes(tc.status) && <Button variant="secondary" onClick={() => act.mutate('disable')}>Disable</Button>}
              <Button variant="secondary" onClick={() => setEditing(true)}>Edit</Button>
              <Button variant="secondary" onClick={() => setRegen(regen === null ? '' : null)}>Regenerate</Button>
              <Button variant="secondary" onClick={() => act.mutate('duplicate')}>Duplicate</Button>
              <Button variant="secondary" onClick={() => setShowVersions(!showVersions)}>History (v{tc.version})</Button>
            </div>
          )}
          {regen !== null && !editing && (
            <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); regenerate.mutate() }}>
              <input aria-label="What should change" className={`${inputCls} mt-0 flex-1`} placeholder="What should change? e.g. also assert the error message"
                value={regen} onChange={(e) => setRegen(e.target.value)} />
              <Button disabled={regenerate.isPending}>{regenerate.isPending ? 'Regenerating…' : 'Regenerate with AI'}</Button>
            </form>
          )}
          {showVersions && <Versions tcId={tc.id} />}
          <ErrorBox error={act.error || regenerate.error || runOne.error} />
        </div>
      )}
    </li>
  )
}

export default function TestCases({ projectId, envs, scans }) {
  const qc = useQueryClient()
  const nav = useNavigate()
  const tests = useQuery({ queryKey: ['tests', projectId], queryFn: () => api(`/projects/${projectId}/test-cases`) })
  const completed = scans.filter((s) => s.status === 'completed')
  const [scanId, setScanId] = useState('')
  const [goals, setGoals] = useState('')
  const [useAi, setUseAi] = useState(true)
  const [sel, setSel] = useState(new Set())
  const [envId, setEnvId] = useState('')
  const gen = useMutation({
    mutationFn: () => api(`/projects/${projectId}/tests/generate`, { method: 'POST', body: { scan_run_id: scanId || completed[0]?.id, goals, use_ai: useAi } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tests', projectId] }),
  })
  const run = useMutation({
    mutationFn: () => api('/test-runs', { method: 'POST', body: { environment_id: envId || envs[0]?.id, test_case_ids: [...sel] } }),
    onSuccess: (r) => nav(`/runs/${r.id}`),
  })
  const approved = tests.data?.filter((t) => t.status === 'approved') || []
  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n })

  return (
    <Card title="Test cases">
      <div className="mb-4 grid gap-3 border-b border-slate-100 pb-4 md:grid-cols-4">
        <Field label="From scan">
          <select className={inputCls} value={scanId} onChange={(e) => setScanId(e.target.value)}>
            {completed.map((s) => <option key={s.id} value={s.id}>{new Date(s.created_at).toLocaleString()} ({s.summary_json.pages} pages)</option>)}
          </select>
        </Field>
        <div className="md:col-span-2">
          <Field label="Testing goals (optional, sent to the AI planner)">
            <input className={inputCls} value={goals} placeholder="e.g. focus on user creation validation" onChange={(e) => setGoals(e.target.value)} />
          </Field>
        </div>
        <div className="flex flex-col justify-end gap-2">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={useAi} onChange={(e) => setUseAi(e.target.checked)} /> Use AI planner</label>
          <Button disabled={!completed.length || gen.isPending} onClick={() => gen.mutate()}>{gen.isPending ? 'Generating…' : 'Generate tests'}</Button>
        </div>
        <div className="md:col-span-4">
          <ErrorBox error={gen.error} />
          {gen.data && (
            <p className="text-sm text-slate-600">
              {gen.data.created} new tests by {gen.data.generated_by} · {gen.data.duplicates_skipped} duplicates skipped ·{' '}
              {gen.data.blocked_by_validator} blocked by validator{gen.data.note && ` · ${gen.data.note}`}
            </p>
          )}
        </div>
      </div>

      {tests.data?.length === 0 && <Empty>No tests yet. Run a discovery scan, then generate tests from it.</Empty>}
      {approved.length > 0 && (
        <div className="mb-2 flex flex-wrap items-center gap-2 text-sm">
          <Button variant="secondary" onClick={() => setSel(new Set(approved.map((t) => t.id)))}>Select all approved ({approved.length})</Button>
          <select className="rounded border border-slate-300 px-2 py-1.5 text-sm" aria-label="Environment" value={envId} onChange={(e) => setEnvId(e.target.value)}>
            {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <Button disabled={!sel.size || run.isPending} onClick={() => run.mutate()}>Run {sel.size} selected</Button>
          <ErrorBox error={run.error} />
        </div>
      )}
      <ul className="divide-y divide-slate-100">
        {tests.data?.map((t) => <TestRow key={t.id} tc={t} selected={sel.has(t.id)} onSelect={() => toggle(t.id)} envId={envId || envs[0]?.id} />)}
      </ul>
    </Card>
  )
}
