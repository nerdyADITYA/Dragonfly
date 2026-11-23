import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api.js'
import { Badge, Button, Card, Empty, ErrorBox, Field, Loading, fmt, inputCls } from '../ui.jsx'

export default function Projects() {
  const qc = useQueryClient()
  const nav = useNavigate()
  const projects = useQuery({ queryKey: ['projects'], queryFn: () => api('/projects') })
  const [form, setForm] = useState({ name: '', description: '' })
  const create = useMutation({
    mutationFn: () => api('/projects', { method: 'POST', body: form }),
    onSuccess: (p) => { qc.invalidateQueries({ queryKey: ['projects'] }); nav(`/projects/${p.id}`) },
  })

  return (
    <>
      <h1 className="text-2xl font-bold">Projects</h1>
      <div className="grid gap-4 md:grid-cols-3">
        <div className="md:col-span-2">
          <Card title="Your projects">
            {projects.isLoading && <Loading />}
            <ErrorBox error={projects.error} />
            {projects.data?.length === 0 && <Empty>No projects yet. Create one to register an application to test.</Empty>}
            <ul className="divide-y divide-slate-100">
              {projects.data?.map((p) => (
                <li key={p.id} className="flex items-center justify-between py-2">
                  <div>
                    <Link className="font-medium text-indigo-700 hover:underline" to={`/projects/${p.id}`}>{p.name}</Link>
                    <p className="text-xs text-slate-500">{p.description || 'No description'} · created {fmt(p.created_at)}</p>
                  </div>
                  <Badge>{p.status}</Badge>
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <Card title="New project">
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
            <Field label="Name"><input className={inputCls} required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Description"><textarea className={inputCls} rows={2} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
            <ErrorBox error={create.error} />
            <Button disabled={create.isPending}>Create project</Button>
          </form>
        </Card>
      </div>
    </>
  )
}
