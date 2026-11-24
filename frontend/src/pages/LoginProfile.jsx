import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api.js'
import { Button, ErrorBox, Field, inputCls } from '../ui.jsx'

const EMPTY = { login_url: '', username: '', password: '', username_selector: '', password_selector: '', submit_selector: '', success_url_contains: '', enabled: true }

/** Target-app sign-in for one environment. The password is write-only: it is never shown again. */
export default function LoginProfile({ env, canEdit }) {
  const qc = useQueryClient()
  const key = ['auth-profile', env.id]
  const profile = useQuery({ queryKey: key, queryFn: () => api(`/environments/${env.id}/auth-profile`) })
  const [f, setF] = useState(null)
  const [advanced, setAdvanced] = useState(false)
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value })
  const refresh = () => qc.invalidateQueries({ queryKey: key })
  const save = useMutation({
    mutationFn: () => api(`/environments/${env.id}/auth-profile`, { method: 'PUT', body: { ...f, password: f.password || null } }),
    onSuccess: () => { setF(null); refresh() },
  })
  const test = useMutation({ mutationFn: () => api(`/environments/${env.id}/auth-profile/test`, { method: 'POST' }) })
  const remove = useMutation({ mutationFn: () => api(`/environments/${env.id}/auth-profile`, { method: 'DELETE' }), onSuccess: refresh })
  const p = profile.data

  if (f) {
    return (
      <form className="mt-2 grid gap-2 rounded border border-slate-200 bg-slate-50 p-3 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        <Field label="Login page URL"><input className={inputCls} required value={f.login_url} placeholder={`${env.base_url}login`} onChange={set('login_url')} /></Field>
        <Field label="Username / email" hint="Use a dedicated test account, never a real person's."><input className={inputCls} required autoComplete="off" value={f.username} onChange={set('username')} /></Field>
        <Field label="Password" hint={p ? 'Leave empty to keep the stored password' : 'Stored encrypted; never shown again'}>
          <input className={inputCls} type="password" autoComplete="new-password" required={!p} value={f.password} onChange={set('password')} />
        </Field>
        <label className="flex items-center gap-2 self-end pb-2 text-sm"><input type="checkbox" checked={f.enabled} onChange={set('enabled')} /> Sign in before scans and test runs</label>
        <button type="button" className="text-left text-xs text-indigo-700 md:col-span-2" onClick={() => setAdvanced(!advanced)}>{advanced ? '▾' : '▸'} Advanced (custom selectors, success check)</button>
        {advanced && <>
          <Field label="Username field (CSS)" hint="Empty = auto-detect"><input className={inputCls} value={f.username_selector} onChange={set('username_selector')} /></Field>
          <Field label="Password field (CSS)" hint="Empty = input[type=password]"><input className={inputCls} value={f.password_selector} onChange={set('password_selector')} /></Field>
          <Field label="Submit button (CSS)" hint="Empty = press Enter"><input className={inputCls} value={f.submit_selector} onChange={set('submit_selector')} /></Field>
          <Field label="Signed in when URL contains" hint="Empty = we left the login page"><input className={inputCls} value={f.success_url_contains} onChange={set('success_url_contains')} /></Field>
        </>}
        <div className="md:col-span-2"><ErrorBox error={save.error} /></div>
        <div className="flex gap-2"><Button disabled={save.isPending}>Save login</Button><Button type="button" variant="secondary" onClick={() => setF(null)}>Cancel</Button></div>
      </form>
    )
  }
  return (
    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-600">
      <span>🔑 {p ? <>Signs in as <strong>{p.username}</strong> at {new URL(p.login_url).pathname}{!p.enabled && ' (disabled)'}</> : 'No login: scans see public pages only.'}</span>
      {canEdit && <button className="text-indigo-700 hover:underline" onClick={() => setF(p ? { ...EMPTY, ...p, password: '' } : { ...EMPTY, login_url: `${env.base_url}login` })}>{p ? 'Edit login' : 'Add login'}</button>}
      {canEdit && p && <button className="text-indigo-700 hover:underline" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? 'Testing…' : 'Test login'}</button>}
      {canEdit && p && <button className="text-red-700 hover:underline" onClick={() => remove.mutate()}>Remove</button>}
      {test.data && <span role="status" className={test.data.ok ? 'text-green-700' : 'text-red-700'}>{test.data.ok ? '✓' : '✗'} {test.data.message}</span>}
      <ErrorBox error={test.error || remove.error} />
    </div>
  )
}
