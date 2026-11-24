import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Link, Route, Routes } from 'react-router-dom'
import './index.css'
import Dashboard from './pages/Dashboard.jsx'
import Execution from './pages/Execution.jsx'
import Finding from './pages/Finding.jsx'
import Project from './pages/Project.jsx'
import Projects from './pages/Projects.jsx'
import Run from './pages/Run.jsx'
import Scan from './pages/Scan.jsx'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl items-center gap-6 px-4 py-3">
            <Link to="/" className="font-bold text-indigo-700">Dragonfly</Link>
            <nav className="flex gap-4 text-sm text-slate-600"><Link to="/">Dashboard</Link><Link to="/projects">Projects</Link></nav>
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
          </Routes>
        </main>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
