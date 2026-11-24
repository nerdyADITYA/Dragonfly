import { useState } from 'react'
import { Button, Field, inputCls } from '../ui.jsx'

// Which inputs each action uses (mirrors backend validator.REQUIRED_FIELDS; optional target marked "?").
const FIELDS = {
  navigate: ['url'], click: ['target'], fill: ['target', 'value'], select: ['target', 'value'], check: ['target'],
  uncheck: ['target'], press: ['target?', 'key'], hover: ['target'], wait_for: ['target'], screenshot: [],
  assert_text: ['target?', 'text'], assert_visible: ['target'], assert_hidden: ['target'], assert_url: ['value'],
  assert_title: ['value'], assert_value: ['target', 'value'], assert_count: ['target', 'count'], assert_no_page_errors: [],
}
// HTTP tests (first step api_request) use only these; the validator rejects mixing the two kinds.
const HTTP_FIELDS = {
  api_request: ['method', 'url', 'headers', 'body', 'value'], assert_status: ['value'], assert_json_schema: ['json_schema'],
  assert_header: ['key', 'value'], assert_header_not: ['key', 'value'], assert_body_not: ['value'], assert_cookies_secure: [],
}
const ALL_FIELDS = { ...FIELDS, ...HTTP_FIELDS }
const VALUE_LABEL = {
  fill: 'Text to type', select: 'Option', assert_url: 'URL contains', assert_title: 'Title contains', assert_value: 'Expected value',
  api_request: 'Body encoding: json or form', assert_status: 'Status, e.g. 404 or 4xx', assert_header: 'Must match (regex, optional)',
  assert_header_not: 'Must NOT match (regex)', assert_body_not: 'Must NOT contain (regex)',
}
const LOCATORS = ['label', 'placeholder', 'test_id', 'text', 'css']
const ROLES = ['', 'button', 'link', 'textbox', 'heading', 'checkbox', 'combobox', 'radio', 'tab', 'listitem', 'table', 'row', 'cell', 'navigation', 'status', 'alert']
const small = 'rounded border border-slate-300 px-2 py-1 text-xs'

function TargetInput({ target = {}, onChange }) {
  const other = LOCATORS.find((k) => target[k]) || 'label'
  const set = (patch) => onChange(Object.fromEntries(Object.entries({ ...target, ...patch }).filter(([, v]) => v)))
  return (
    <div className="flex flex-wrap items-center gap-1">
      <span className="text-xs text-slate-500">find by</span>
      <select aria-label="Role" className={small} value={target.role || ''} onChange={(e) => set({ role: e.target.value })}>
        {ROLES.map((r) => <option key={r} value={r}>{r ? `role: ${r}` : 'no role'}</option>)}
      </select>
      {target.role && <input aria-label="Accessible name" placeholder="name, e.g. Sign in" className={small} value={target.name || ''} onChange={(e) => set({ name: e.target.value })} />}
      <span className="text-xs text-slate-500">or</span>
      <select aria-label="Locator type" className={small} value={other}
        onChange={(e) => set({ [other]: '', [e.target.value]: target[other] || '' })}>
        {LOCATORS.map((k) => <option key={k}>{k}</option>)}
      </select>
      <input aria-label={`Locator ${other}`} className={small} value={target[other] || ''} onChange={(e) => set({ [other]: e.target.value })} />
    </div>
  )
}

function StepRow({ step, i, n, http, onChange, onMove, onRemove }) {
  const f = ALL_FIELDS[step.type] || []
  const set = (patch) => onChange({ ...step, ...patch })
  return (
    <li className={`rounded border p-2 ${step.type.startsWith('assert') ? 'border-indigo-200 bg-indigo-50/40' : 'border-slate-200 bg-white'}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="w-5 text-xs text-slate-400">{i + 1}</span>
        <select aria-label={`Step ${i + 1} action`} className={small} value={step.type}
          onChange={(e) => onChange({ type: e.target.value, description: step.description, target: step.target })}>
          {Object.keys(http ? HTTP_FIELDS : FIELDS).map((t) => <option key={t} value={t}>{t.replaceAll('_', ' ')}</option>)}
        </select>
        {f.includes('method') && (
          <select aria-label="HTTP method" className={small} value={step.method || 'GET'} onChange={(e) => set({ method: e.target.value })}>
            {['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'].map((m) => <option key={m}>{m}</option>)}
          </select>
        )}
        {f.includes('url') && <input aria-label="URL" placeholder="https://…" className={`${small} flex-1`} value={step.url || ''} onChange={(e) => set({ url: e.target.value })} />}
        {f.includes('value') && <input aria-label={VALUE_LABEL[step.type]} placeholder={VALUE_LABEL[step.type]} className={small} value={step.value || ''} onChange={(e) => set({ value: e.target.value })} />}
        {f.includes('text') && <input aria-label="Expected text" placeholder="expected text" className={small} value={step.text || ''} onChange={(e) => set({ text: e.target.value })} />}
        {f.includes('key') && (http
          ? <input aria-label="Header name" placeholder="Header name" className={small} value={step.key || ''} onChange={(e) => set({ key: e.target.value })} />
          : <input aria-label="Key" placeholder="Enter" className={`${small} w-20`} value={step.key || ''} onChange={(e) => set({ key: e.target.value })} />)}
        {f.includes('count') && <input aria-label="Count" type="number" min="0" className={`${small} w-16`} value={step.count ?? ''} onChange={(e) => set({ count: e.target.value === '' ? null : +e.target.value })} />}
        <span className="ml-auto flex gap-1">
          <button type="button" aria-label="Move up" disabled={i === 0} className="px-1 disabled:opacity-30" onClick={() => onMove(-1)}>↑</button>
          <button type="button" aria-label="Move down" disabled={i === n - 1} className="px-1 disabled:opacity-30" onClick={() => onMove(1)}>↓</button>
          <button type="button" aria-label="Remove step" className="px-1 text-red-700" onClick={onRemove}>✕</button>
        </span>
      </div>
      {['headers', 'body', 'json_schema'].filter((k) => f.includes(k)).map((k) => (
        <textarea key={k} aria-label={k} rows={k === 'json_schema' ? 4 : 2} placeholder={`${k.replace('_', ' ')} (JSON, optional)`}
          className={`${small} mt-1 ml-7 w-[calc(100%-1.75rem)] font-mono`} value={step[k] || ''} onChange={(e) => set({ [k]: e.target.value || null })} />
      ))}
      {(f.includes('target') || f.includes('target?')) && <div className="mt-1 ml-7"><TargetInput target={step.target || {}} onChange={(target) => set({ target })} /></div>}
      <input aria-label="Step description" placeholder="description (optional, shown in bug reports)" className={`${small} mt-1 ml-7 w-[calc(100%-1.75rem)]`}
        value={step.description || ''} onChange={(e) => set({ description: e.target.value })} />
    </li>
  )
}

/** Structured editor for a test definition (§36), with a raw-JSON escape hatch. */
export default function TestEditor({ definition, onSave, onCancel, saving }) {
  const [d, setD] = useState(() => structuredClone(definition))
  const [json, setJson] = useState(null)
  const [jsonError, setJsonError] = useState(null)
  const set = (patch) => setD({ ...d, ...patch })
  const http = d.steps[0]?.type === 'api_request'
  const setStep = (i, s) => set({ steps: d.steps.map((x, j) => (j === i ? s : x)) })
  const move = (i, dir) => { const s = [...d.steps]; [s[i], s[i + dir]] = [s[i + dir], s[i]]; set({ steps: s }) }
  const lines = (v) => v.split('\n').map((x) => x.trim()).filter(Boolean)
  const sel = (k, opts) => (
    <select className={inputCls} value={d[k]} onChange={(e) => set({ [k]: e.target.value })}>{opts.map((o) => <option key={o}>{o}</option>)}</select>
  )

  const save = () => {
    if (json === null) return onSave(d)
    try { onSave(JSON.parse(json)); setJsonError(null) } catch (e) { setJsonError(e.message) }
  }
  return (
    <div className="space-y-3 rounded border border-indigo-200 bg-white p-3">
      {json !== null ? (
        <textarea aria-label="Test definition JSON" className={`${inputCls} font-mono text-xs`} rows={18} value={json} onChange={(e) => setJson(e.target.value)} />
      ) : (
        <>
          <div className="grid gap-2 md:grid-cols-4">
            <div className="md:col-span-3"><Field label="Title"><input className={inputCls} value={d.title} onChange={(e) => set({ title: e.target.value })} /></Field></div>
            <Field label="Key"><input className={inputCls} value={d.key} onChange={(e) => set({ key: e.target.value })} /></Field>
            <Field label="Category">{sel('category', ['functional', 'validation', 'edge_case', 'regression', 'accessibility', 'api', 'security'])}</Field>
            <Field label="Priority">{sel('priority', ['P0', 'P1', 'P2', 'P3'])}</Field>
            <Field label="Risk">{sel('risk', ['low', 'medium', 'high'])}</Field>
            <Field label="Side effect">{sel('side_effect', ['none', 'writes_data', 'destructive'])}</Field>
          </div>
          <Field label="Description"><textarea className={inputCls} rows={2} value={d.description} onChange={(e) => set({ description: e.target.value })} /></Field>
          <Field label="Target URL"><input className={inputCls} value={d.target_url} onChange={(e) => set({ target_url: e.target.value })} /></Field>
          <div>
            <p className="text-sm font-medium">Steps <span className="text-xs font-normal text-slate-500">(at least one assertion; first step must open a page)</span></p>
            <ol className="mt-1 space-y-1">
              {d.steps.map((s, i) => (
                <StepRow key={i} step={s} i={i} n={d.steps.length} http={http} onChange={(x) => setStep(i, x)} onMove={(dir) => move(i, dir)}
                  onRemove={() => set({ steps: d.steps.filter((_, j) => j !== i) })} />
              ))}
            </ol>
            <div className="mt-1 flex gap-2">
              <Button type="button" variant="secondary" onClick={() => set({ steps: [...d.steps, http
                ? { type: 'api_request', method: 'GET', url: d.target_url, description: '' } : { type: 'click', target: {}, description: '' }] })}>{http ? '+ Request' : '+ Action'}</Button>
              <Button type="button" variant="secondary" onClick={() => set({ steps: [...d.steps, http
                ? { type: 'assert_status', value: '200', description: '' } : { type: 'assert_text', text: '', description: '' }] })}>+ Assertion</Button>
            </div>
          </div>
          <Field label="Expected outcomes (one per line)">
            <textarea className={inputCls} rows={2} value={d.expected_outcomes.join('\n')} onChange={(e) => set({ expected_outcomes: lines(e.target.value) })} />
          </Field>
        </>
      )}
      {jsonError && <p role="alert" className="text-sm text-red-700">Invalid JSON: {jsonError}</p>}
      <div className="flex flex-wrap gap-2">
        <Button type="button" disabled={saving} onClick={save}>Save (returns to draft)</Button>
        <Button type="button" variant="secondary" onClick={onCancel}>Cancel</Button>
        <Button type="button" variant="secondary" className="ml-auto" onClick={() => {
          if (json === null) return setJson(JSON.stringify(d, null, 2))
          try { setD(JSON.parse(json)); setJson(null); setJsonError(null) } catch (e) { setJsonError(e.message) }
        }}>
          {json === null ? 'Advanced: edit JSON' : 'Back to form'}
        </Button>
      </div>
    </div>
  )
}
