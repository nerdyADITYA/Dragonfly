import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useEffect, useState } from 'react'
import { api } from './api.js'
import { Button, Card, ErrorBox, Field, Loading, inputCls } from './ui.jsx'

const MeContext = createContext(null)
const RANK = { viewer: 0, member: 1, admin: 2, owner: 3 }

/** Current user: { email, display_name, role, organization, can(role) }. */
export function useMe() {
  return useContext(MeContext)
}

function SignIn() {
  const qc = useQueryClient()
  const [f, setF] = useState({ email: '', password: '' })
  const login = useMutation({ mutationFn: () => api('/auth/login', { method: 'POST', body: f }), onSuccess: () => qc.resetQueries() })
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); login.mutate() }}>
      <Field label="Email"><input className={inputCls} type="email" autoComplete="username" required value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
      <Field label="Password"><input className={inputCls} type="password" autoComplete="current-password" required value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Field>
      <ErrorBox error={login.error} />
      <Button className="w-full" disabled={login.isPending}>Sign in</Button>
    </form>
  )
}

function Setup() {
  const qc = useQueryClient()
  const [f, setF] = useState({ organization: '', display_name: '', email: '', password: '' })
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const reg = useMutation({ mutationFn: () => api('/auth/register', { method: 'POST', body: f }), onSuccess: () => qc.resetQueries() })
  return (
    <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); reg.mutate() }}>
      <p className="text-sm text-slate-600">First run: create your organization and its owner account. Existing projects are moved into it.</p>
      <Field label="Organization"><input className={inputCls} required value={f.organization} onChange={set('organization')} /></Field>
      <Field label="Your name"><input className={inputCls} required value={f.display_name} onChange={set('display_name')} /></Field>
      <Field label="Email"><input className={inputCls} type="email" autoComplete="username" required value={f.email} onChange={set('email')} /></Field>
      <Field label="Password" hint="At least 10 characters">
        <input className={inputCls} type="password" autoComplete="new-password" minLength={10} required value={f.password} onChange={set('password')} />
      </Field>
      <ErrorBox error={reg.error} />
      <Button className="w-full" disabled={reg.isPending}>Create organization</Button>
    </form>
  )
}

/** Renders children only for a signed-in user; otherwise first-run setup or sign-in. */
export function AuthGate({ children }) {
  const qc = useQueryClient()
  const me = useQuery({ queryKey: ['me'], queryFn: () => api('/auth/me'), retry: false })
  const status = useQuery({ queryKey: ['auth-status'], queryFn: () => api('/auth/status'), enabled: me.isError })
  useEffect(() => {
    const onOut = () => qc.resetQueries({ queryKey: ['me'] })
    window.addEventListener('df-signed-out', onOut)
    return () => window.removeEventListener('df-signed-out', onOut)
  }, [qc])

  if (me.isLoading) return <main className="mx-auto max-w-sm px-4 py-16"><Loading /></main>
  if (me.data) {
    const value = { ...me.data, can: (role) => RANK[me.data.role] >= RANK[role] }
    return <MeContext.Provider value={value}>{children}</MeContext.Provider>
  }
  return (
    <main className="mx-auto max-w-sm px-4 py-16">
      <h1 className="mb-1 text-2xl font-bold text-indigo-700">Dragonfly</h1>
      <p className="mb-6 text-sm text-slate-500">AI-assisted QA that brings evidence.</p>
      <Card title={status.data?.setup_required ? 'Set up Dragonfly' : 'Sign in'}>
        {status.isLoading ? <Loading /> : status.data?.setup_required ? <Setup /> : <SignIn />}
      </Card>
    </main>
  )
}

export function SignOutButton() {
  const qc = useQueryClient()
  const out = useMutation({ mutationFn: () => api('/auth/logout', { method: 'POST' }), onSettled: () => { qc.clear(); qc.resetQueries({ queryKey: ['me'] }) } })
  return <button className="text-sm text-slate-600 hover:text-slate-900" onClick={() => out.mutate()}>Sign out</button>
}
