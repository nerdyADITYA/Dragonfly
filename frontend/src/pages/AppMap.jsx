import { useQuery } from '@tanstack/react-query'
import { Background, Controls, MarkerType, MiniMap, ReactFlow } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo, useState } from 'react'
import { api, artifactUrl } from '../api.js'
import { Card, inputCls } from '../ui.jsx'

// Page state → colour: red = open findings, amber = no tests yet, green = covered, no open findings.
const tone = (n) => (n.open_findings ? '#dc2626' : n.tests ? '#16a34a' : '#d97706')

/** Application map (§8.5): pages by discovery depth, navigation edges, coverage overlays. */
export default function AppMap({ scanId }) {
  const map = useQuery({ queryKey: ['map', scanId], queryFn: () => api(`/discovery/${scanId}/map`) })
  const [search, setSearch] = useState('')
  const [show, setShow] = useState('all')
  const [selected, setSelected] = useState(null)

  const { nodes, edges } = useMemo(() => {
    const data = map.data || { nodes: [], edges: [] }
    const row = {}
    const q = search.trim().toLowerCase()
    const nodes = data.nodes.map((n) => {
      const y = (row[n.depth] = (row[n.depth] ?? -1) + 1)
      const path = new URL(n.url).pathname + new URL(n.url).search
      const hit = (!q || `${n.title} ${path}`.toLowerCase().includes(q))
        && (show === 'all' || (show === 'findings' ? n.open_findings > 0 : n.tests === 0))
      const label = (
        <div className="text-left">
          <div className="truncate font-semibold">{n.title || path}</div>
          <div className="truncate font-mono text-[10px] text-slate-500">{path}</div>
          <div className="mt-1 text-[10px]">{n.tests} tests · {n.open_findings} open findings</div>
        </div>
      )
      return {
        id: n.id, position: { x: n.depth * 280, y: y * 110 }, data: { ...n, path, label },
        style: { border: `2px solid ${tone(n)}`, borderRadius: 8, padding: 6, width: 220, fontSize: 12,
          opacity: hit ? 1 : 0.25, background: selected?.id === n.id ? '#eef2ff' : 'white' },
      }
    })
    const seen = new Set()
    const edges = data.edges.filter((e) => e.source !== e.target && !seen.has(e.source + e.target) && seen.add(e.source + e.target))
      .map((e) => ({ id: e.source + e.target, source: e.source, target: e.target, markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: '#94a3b8' } }))
    return { nodes, edges }
  }, [map.data, search, show, selected])

  if (!map.data) return null
  return (
    <Card title="Application map" actions={
      <>
        <input aria-label="Search pages" placeholder="Search pages" className={`${inputCls} mt-0 w-40`} value={search} onChange={(e) => setSearch(e.target.value)} />
        <select aria-label="Highlight" className="rounded border border-slate-300 px-2 py-1 text-sm" value={show} onChange={(e) => setShow(e.target.value)}>
          <option value="all">all pages</option><option value="findings">with open findings</option><option value="untested">without tests</option>
        </select>
      </>
    }>
      <p className="mb-2 flex gap-4 text-xs text-slate-600">
        <span><span className="inline-block h-2 w-2 rounded-full bg-red-600" /> open findings</span>
        <span><span className="inline-block h-2 w-2 rounded-full bg-amber-600" /> no tests</span>
        <span><span className="inline-block h-2 w-2 rounded-full bg-green-600" /> tested, no open findings</span>
        <span>Columns = discovery depth · drag to pan · scroll to zoom</span>
      </p>
      <div className="grid gap-3 md:grid-cols-4">
        {/* xyflow themes via CSS light-dark() and its `.light` ancestor rule; the app is light-only */}
        <div className="light h-96 rounded border border-slate-200 md:col-span-3">
          <ReactFlow nodes={nodes} edges={edges} fitView nodesConnectable={false} nodesDraggable={false}
            onNodeClick={(_, n) => setSelected(n.data)} proOptions={{ hideAttribution: true }}>
            <Background /><Controls showInteractive={false} /><MiniMap pannable zoomable />
          </ReactFlow>
        </div>
        <div className="text-sm">
          {selected ? (
            <div className="space-y-1">
              <p className="font-semibold">{selected.title || selected.path}</p>
              <p className="break-all font-mono text-xs text-slate-500">{selected.url}</p>
              <p>{selected.tests} tests · {selected.open_findings} open findings · depth {selected.depth}</p>
              {selected.screenshot_artifact_id && <img src={artifactUrl(selected.screenshot_artifact_id)} alt={`Screenshot of ${selected.path}`} className="rounded border" />}
            </div>
          ) : <p className="text-slate-500">Click a page for details.</p>}
        </div>
      </div>
    </Card>
  )
}
