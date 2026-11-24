import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api.js'
import { useMe } from '../Auth.jsx'
import { Badge, Button, Card, ErrorBox, Field, inputCls } from '../ui.jsx'

const ROLE_HELP = {
  viewer: 'Read-only',
  member: 'Run scans and tests, edit tests, triage findings, tickets, retests',
  admin: 'Member + projects, environments, scope, login profiles, developers, team',
  owner: 'Admin + manage owners',
}

function ChangePassword() {
  const [f, setF] = useState({ current_password: '', new_password: '' })
  const save = useMutation({ mutationFn: () => api('/auth/password', { method: 'POST', body: f }), onSuccess: () => setF({ current_password: '', new_password: '' }) })
  return (
    <Card title="Your password">
      <form className="space-y-2" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        <Field label="Current password"><input className={inputCls} type="password" autoComplete="current-password" required value={f.current_password} onChange={(e) => setF({ ...f, current_password: e.target.value })} /></Field>
        <Field label="New password" hint="At least 10 characters. Other sessions are signed out.">
          <input className={inputCls} type="password" autoComplete="new-password" minLength={10} required value={f.new_password} onChange={(e) => setF({ ...f, new_password: e.target.value })} />
        </Field>
        <ErrorBox error={save.error} />
        {save.isSuccess && <p className="text-sm text-green-700" role="status">Password changed.</p>}
        <Button disabled={save.isPending}>Change password</Button>
      </form>
    </Card>
  )
}

export default function Team() {
  const me = useMe()
  const qc = useQueryClient()
  const members = useQuery({ queryKey: ['members'], queryFn: () => api('/org/members') })
  const [f, setF] = useState({ email: '', display_name: '', role: 'member', password: '' })
  const refresh = () => qc.invalidateQueries({ queryKey: ['members'] })
  const add = useMutation({ mutationFn: () => api('/org/members', { method: 'POST', body: f }), onSuccess: () => { setF({ email: '', display_name: '', role: 'member', password: '' }); refresh() } })
  const setRole = useMutation({ mutationFn: ({ id, role }) => api(`/org/members/${id}`, { method: 'PATCH', body: { role } }), onSuccess: refresh })
  const remove = useMutation({ mutationFn: (id) => api(`/org/members/${id}`, { method: 'DELETE' }), onSuccess: refresh })
  const admin = me.can('admin')
  const roles = me.role === 'owner' ? ['viewer', 'member', 'admin', 'owner'] : ['viewer', 'member', 'admin']

  return (
    <>
      <h1 className="text-2xl font-bold">Team · {me.organization.name}</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="space-y-4 md:col-span-2">
          <Card title="Members">
            <table className="w-full text-sm">
              <tbody className="divide-y divide-slate-100">
                {members.data?.map((m) => (
                  <tr key={m.user_id}>
                    <td className="py-2">{m.display_name}<br /><span className="text-xs text-slate-500">{m.email}</span></td>
                    <td>
                      {admin && m.user_id !== me.id && (m.role !== 'owner' || me.role === 'owner') ? (
                        <select aria-label={`Role of ${m.email}`} className="rounded border border-slate-300 px-2 py-1 text-sm" value={m.role}
                          onChange={(e) => setRole.mutate({ id: m.user_id, role: e.target.value })}>
                          {[...new Set([m.role, ...roles])].map((r) => <option key={r}>{r}</option>)}
                        </select>
                      ) : <Badge>{m.role}</Badge>}
                    </td>
                    <td className="text-right">
                      {admin && m.user_id !== me.id && (m.role !== 'owner' || me.role === 'owner') && (
                        <button className="text-xs text-red-700 hover:underline" onClick={() => remove.mutate(m.user_id)}>Remove</button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <ErrorBox error={setRole.error || remove.error} />
          </Card>
          {admin && (
            <Card title="Add a member">
              <form className="grid gap-2 md:grid-cols-2" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
                <Field label="Name"><input className={inputCls} required value={f.display_name} onChange={(e) => setF({ ...f, display_name: e.target.value })} /></Field>
                <Field label="Email"><input className={inputCls} type="email" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
                <Field label="Role" hint={ROLE_HELP[f.role]}>
                  <select className={inputCls} value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{roles.map((r) => <option key={r}>{r}</option>)}</select>
                </Field>
                <Field label="Initial password" hint="Share it securely; they can change it after signing in.">
                  <input className={inputCls} type="password" autoComplete="new-password" minLength={10} required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
                </Field>
                <div className="md:col-span-2"><ErrorBox error={add.error} /></div>
                <div><Button disabled={add.isPending}>Add member</Button></div>
              </form>
            </Card>
          )}
        </div>
        <div className="space-y-4">
          <Card title="Roles">
            <ul className="space-y-1 text-sm">{Object.entries(ROLE_HELP).map(([r, h]) => <li key={r}><Badge>{r}</Badge> {h}</li>)}</ul>
          </Card>
          <ChangePassword />
        </div>
      </div>
    </>
  )
}
