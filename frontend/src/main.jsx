import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import { AuthGate, SignOutButton, useMe } from './Auth.jsx'
import './index.css'
import Dashboard from './pages/Dashboard.jsx'
import Execution from './pages/Execution.jsx'
import Finding from './pages/Finding.jsx'
import Project from './pages/Project.jsx'
import Projects from './pages/Projects.jsx'
import Run from './pages/Run.jsx'
import Scan from './pages/Scan.jsx'
import Team from './pages/Team.jsx'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

function Shell() {
  const me = useMe()
  return (
    <>
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-6 px-4 py-3">
          <Link to="/" className="font-bold text-indigo-700">Dragonfly</Link>
          <nav className="flex gap-4 text-sm text-slate-600"><Link to="/">Dashboard</Link><Link to="/projects">Projects</Link><Link to="/team">Team</Link></nav>
          <div className="ml-auto flex items-center gap-3 text-sm">
            <span className="text-slate-600">{me.display_name} · {me.organization.name} <span className="text-xs text-slate-400">({me.role})</span></span>
            <SignOutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-6xl space-y-4 px-4 py-6">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects" element={<Projects />} />
          <Route path="/projects/:id" element={<Project />} />
          <Route path="/scans/:id" element={<Scan />} />
          <Route path="/runs/:id" element={<Run />} />
          <Route path="/executions/:id" element={<Execution />} />
          <Route path="/findings/:id" element={<Finding />} />
          <Route path="/team" element={<Team />} />
        </Routes>
      </main>
    </>
  )
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <AuthGate><Shell /></AuthGate>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
