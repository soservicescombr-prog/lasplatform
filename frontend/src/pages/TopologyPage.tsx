// netguard/frontend/src/pages/TopologyPage.tsx
import { useEffect, useState, useRef } from 'react'
import api from '@/services/api'
import { Network, RefreshCw, ZoomIn, ZoomOut, Maximize2 } from 'lucide-react'

interface TopoNode { id: string; label: string; ip: string; type: string; status: string; vendor: string | null; snmp: boolean; x?: number; y?: number }
interface TopoEdge { id: string; source: string; target: string; type: string; status: string }

const typeColors: Record<string, string> = {
  switch: '#3b82f6', router: '#8b5cf6', firewall: '#ef4444', server: '#22c55e',
  desktop: '#6b7280', printer: '#f59e0b', access_point: '#06b6d4', unknown: '#9ca3af',
}

export function TopologyPage() {
  const [nodes, setNodes] = useState<TopoNode[]>([])
  const [edges, setEdges] = useState<TopoEdge[]>([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<TopoNode | null>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const [zoom, setZoom] = useState(1)

  const fetchTopology = async () => {
    setLoading(true)
    try {
      const { data } = await api.get('/extras/topology/data')
      // Position nodes in a force-directed-like layout (simple circular)
      const positioned = data.nodes.map((n: TopoNode, i: number) => {
        const angle = (2 * Math.PI * i) / data.nodes.length
        const radius = Math.min(300, data.nodes.length * 15)
        return { ...n, x: 450 + radius * Math.cos(angle), y: 350 + radius * Math.sin(angle) }
      })
      setNodes(positioned)
      setEdges(data.edges)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchTopology() }, [])

  useEffect(() => {
    if (!canvasRef.current || nodes.length === 0) return
    const canvas = canvasRef.current
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const w = canvas.width
    const h = canvas.height
    ctx.clearRect(0, 0, w, h)
    ctx.save()
    ctx.scale(zoom, zoom)

    // Draw edges
    edges.forEach(e => {
      const src = nodes.find(n => n.id === e.source)
      const tgt = nodes.find(n => n.id === e.target)
      if (!src?.x || !tgt?.x) return
      ctx.beginPath()
      ctx.moveTo(src.x, src.y!)
      ctx.lineTo(tgt.x, tgt.y!)
      ctx.strokeStyle = e.type === 'inferred' ? '#d1d5db' : '#9ca3af'
      ctx.lineWidth = e.type === 'inferred' ? 1 : 2
      if (e.type === 'inferred') ctx.setLineDash([4, 4])
      else ctx.setLineDash([])
      ctx.stroke()
    })

    // Draw nodes
    nodes.forEach(n => {
      if (n.x == null || n.y == null) return
      const color = typeColors[n.type] || '#9ca3af'
      const radius = n.type === 'switch' || n.type === 'router' ? 18 : 14

      // Glow for online
      if (n.status === 'online') {
        ctx.beginPath()
        ctx.arc(n.x, n.y, radius + 4, 0, 2 * Math.PI)
        ctx.fillStyle = color + '30'
        ctx.fill()
      }

      // Circle
      ctx.beginPath()
      ctx.arc(n.x, n.y, radius, 0, 2 * Math.PI)
      ctx.fillStyle = selected?.id === n.id ? '#1a5ff5' : color
      ctx.fill()
      ctx.strokeStyle = '#fff'
      ctx.lineWidth = 2
      ctx.stroke()

      // Label
      ctx.fillStyle = '#374151'
      ctx.font = '10px Inter, sans-serif'
      ctx.textAlign = 'center'
      ctx.fillText(n.label.substring(0, 18), n.x, n.y + radius + 14)
      ctx.fillStyle = '#9ca3af'
      ctx.font = '9px monospace'
      ctx.fillText(n.ip, n.x, n.y + radius + 25)
    })

    ctx.restore()
  }, [nodes, edges, zoom, selected])

  const handleCanvasClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current
    if (!canvas) return
    const rect = canvas.getBoundingClientRect()
    const x = (e.clientX - rect.left) / zoom
    const y = (e.clientY - rect.top) / zoom

    const clicked = nodes.find(n =>
      n.x && n.y && Math.sqrt((n.x - x) ** 2 + (n.y - y) ** 2) < 20
    )
    setSelected(clicked || null)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Topologia de Rede</h1>
          <p className="text-sm text-surface-500 mt-0.5">{nodes.length} dispositivos · {edges.length} conexões</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setZoom(z => Math.max(0.5, z - 0.2))} className="btn-secondary btn-sm"><ZoomOut className="w-4 h-4" /></button>
          <button onClick={() => setZoom(z => Math.min(2, z + 0.2))} className="btn-secondary btn-sm"><ZoomIn className="w-4 h-4" /></button>
          <button onClick={() => setZoom(1)} className="btn-secondary btn-sm"><Maximize2 className="w-4 h-4" /></button>
          <button onClick={fetchTopology} className="btn-secondary btn-sm"><RefreshCw className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="card overflow-hidden relative">
        {loading ? (
          <div className="flex items-center justify-center h-[600px] text-surface-400">Carregando topologia...</div>
        ) : nodes.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-[600px] text-surface-400">
            <Network className="w-12 h-12 mb-3 opacity-40" />
            <p>Nenhum dispositivo encontrado. Execute um Discovery Scan primeiro.</p>
          </div>
        ) : (
          <canvas ref={canvasRef} width={900} height={700} onClick={handleCanvasClick}
            className="w-full cursor-crosshair bg-white dark:bg-surface-900" />
        )}

        {/* Legend */}
        <div className="absolute bottom-4 left-4 bg-white/90 dark:bg-surface-800/90 rounded-lg p-3 text-xs space-y-1 border border-surface-200 dark:border-surface-700">
          {Object.entries(typeColors).map(([type, color]) => (
            <div key={type} className="flex items-center gap-2">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: color }} />
              <span className="capitalize text-surface-600 dark:text-surface-400">{type}</span>
            </div>
          ))}
        </div>

        {/* Selected node detail */}
        {selected && (
          <div className="absolute top-4 right-4 bg-white dark:bg-surface-800 rounded-lg p-4 shadow-lg border border-surface-200 dark:border-surface-700 w-64">
            <h3 className="font-medium text-surface-900 dark:text-white">{selected.label}</h3>
            <div className="mt-2 space-y-1 text-xs text-surface-600 dark:text-surface-400">
              <p><span className="font-medium">IP:</span> {selected.ip}</p>
              <p><span className="font-medium">Tipo:</span> <span className="capitalize">{selected.type}</span></p>
              <p><span className="font-medium">Status:</span> {selected.status}</p>
              {selected.vendor && <p><span className="font-medium">Fabricante:</span> {selected.vendor}</p>}
              <p><span className="font-medium">SNMP:</span> {selected.snmp ? 'Ativo' : 'Inativo'}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
