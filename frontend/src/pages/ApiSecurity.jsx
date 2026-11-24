import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api.js'
import { useMe } from '../Auth.jsx'
import { Badge, Button, Card, Empty, ErrorBox, Field, inputCls } from '../ui.jsx'

const PROFILES = {
  off: 'No security checks.',
  passive: 'Read-only: security headers, cookie flags, error-page leaks, CORS. No state changes.',
  standard: 'Passive + low-volume probes, e.g. one failed sign-in with a fake account to check error disclosure.',
}

/** API inventory + security policy + API/security test generation for one environment (§11, §12). */
export default function ApiSecurityCard({ projectId, envs, scans }) {
  const admin = useMe().can('admin')  // scan policy is admin-only
  const qc = useQueryClient()
  const [envId, setEnvId] = useState('')
  const env = envs.find((e) => e.id === envId) || envs[0]
  const [specUrl, setSpecUrl] = useState('')
  const [pasted, setPasted] = useState(null)
  const endpoints = useQuery({ queryKey: ['endpoints', env?.id], queryFn: () => api(`/environments/${env.id}/endpoints`), enabled: !!env })
  const scan = scans.find((s) => s.environment_id === env?.id && s.status === 'completed')
  const policy = env?.scan_policy || {}

  const savePolicy = useMutation({
    mutationFn: (patch) => api(`/environments/${env.id}`, { method: 'PATCH', body: { scan_policy: { ...policy, ...patch } } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['envs', projectId] }),
  })
  const importSpec = useMutation({
    mutationFn: () => {
      if (pasted !== null) {
        let spec
        try { spec = JSON.parse(pasted) } catch { throw new Error('Pasted spec is not valid JSON') }
        return api(`/environments/${env.id}/openapi`, { method: 'POST', body: { spec } })
      }
      return api(`/environments/${env.id}/openapi`, { method: 'POST', body: { url: specUrl || `${env.base_url}openapi.json` } })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['endpoints', env.id] }),
  })
  const generate = useMutation({
    mutationFn: () => api(`/projects/${projectId}/tests/generate-api`, { method: 'POST', body: { scan_run_id: scan.id } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tests', projectId] }),
  })

  if (!env) return null
  return (
    <Card title="API & security testing" actions={envs.length > 1 && (
      <select aria-label="Environment" className="rounded border border-slate-300 px-2 py-1 text-sm" value={env.id} onChange={(e) => setEnvId(e.target.value)}>
        {envs.map((e) => <option key={e.id} value={e.id}>{e.name}</option>)}
      </select>
    )}>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-2">
          <Field label="Security profile" hint={PROFILES[policy.security_profile || 'passive']}>
            <select className={inputCls} value={policy.security_profile || 'passive'} disabled={!admin || savePolicy.isPending}
              onChange={(e) => savePolicy.mutate({ security_profile: e.target.value })}>
              {Object.keys(PROFILES).map((p) => <option key={p}>{p}</option>)}
            </select>
          </Field>
          <Field label="Rate limit (requests/second)" hint={`Budget: ${policy.max_requests ?? 200} requests per test run`}>
            <input className={inputCls} type="number" min="0.1" max="50" step="0.1" disabled={!admin} defaultValue={policy.requests_per_second ?? 5}
              onBlur={(e) => +e.target.value !== policy.requests_per_second && savePolicy.mutate({ requests_per_second: +e.target.value })} />
          </Field>
          <ErrorBox error={savePolicy.error} />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Import OpenAPI</p>
          {pasted === null ? (
            <input aria-label="OpenAPI spec URL" className={`${inputCls} mt-0`} placeholder={`${env.base_url}openapi.json`} value={specUrl} onChange={(e) => setSpecUrl(e.target.value)} />
          ) : (
            <textarea aria-label="OpenAPI spec JSON" className={`${inputCls} mt-0 font-mono text-xs`} rows={4} placeholder='{"openapi": "3.1.0", "paths": {…}}' value={pasted} onChange={(e) => setPasted(e.target.value)} />
          )}
          <div className="flex flex-wrap gap-2">
            <Button disabled={importSpec.isPending} onClick={() => importSpec.mutate()}>{importSpec.isPending ? 'Importing…' : 'Import'}</Button>
            <Button variant="secondary" onClick={() => setPasted(pasted === null ? '' : null)}>{pasted === null ? 'Paste JSON instead' : 'Use a URL instead'}</Button>
          </div>
          <p className="text-xs text-slate-500">The URL must be inside this environment's scope. Endpoints seen as XHR/fetch during discovery are added automatically.</p>
          <ErrorBox error={importSpec.error} />
          {importSpec.data && <p className="text-xs text-slate-600">{importSpec.data.created} new, {importSpec.data.updated} updated</p>}
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Generate tests</p>
          <p className="text-xs text-slate-500">
            Rule-based API tests (status, schema, not-found and malformed ids) for safe GET endpoints, plus security checks for the
            selected profile. They arrive as drafts for review, like other tests.
          </p>
          <Button disabled={!scan || generate.isPending} onClick={() => generate.mutate()}>Generate API & security tests</Button>
          {!scan && <p className="text-xs text-amber-700">Run a discovery scan on this environment first.</p>}
          <ErrorBox error={generate.error} />
          {generate.data && (
            <div className="text-xs text-slate-600">
              <p>{generate.data.created} new ({generate.data.by_category.api} API, {generate.data.by_category.security} security) ·{' '}
                {generate.data.duplicates_skipped} duplicates · {generate.data.blocked_by_validator} blocked</p>
              {generate.data.skipped_endpoints.length > 0 && (
                <details><summary className="cursor-pointer">{generate.data.skipped_endpoints.length} endpoints skipped</summary>
                  <ul>{generate.data.skipped_endpoints.map((s, i) => <li key={i}><span className="font-mono">{s.endpoint}</span>: {s.reason}</li>)}</ul>
                </details>
              )}
            </div>
          )}
        </div>
      </div>

      <div className="mt-4 border-t border-slate-100 pt-3">
        <p className="mb-1 text-sm font-medium">Endpoint inventory ({endpoints.data?.length ?? 0})</p>
        {endpoints.data?.length === 0 && <Empty>No endpoints yet. Import an OpenAPI spec, or run discovery on an app that calls APIs.</Empty>}
        <div className="max-h-64 overflow-auto">
          <table className="w-full text-xs">
            <tbody className="divide-y divide-slate-100">
              {endpoints.data?.map((e) => (
                <tr key={e.id}>
                  <td className="py-1 pr-2 font-mono font-semibold">{e.method}</td>
                  <td className="pr-2 font-mono">{e.path}</td>
                  <td className="pr-2 text-slate-500">{e.summary}</td>
                  <td className="pr-2 text-slate-500">{e.response_content_type}</td>
                  <td><Badge>{e.source}</Badge></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Card>
  )
}
