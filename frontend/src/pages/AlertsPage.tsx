// netguard/frontend/src/pages/AlertsPage.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { alertsApi } from '@/services/api'
import type { Alert, AlertSummary } from '@/types'
import { cn, formatDate } from '@/lib/utils'
import { Bell, BellOff, Check, CheckCheck, VolumeX, Volume2 } from 'lucide-react'
import toast from 'react-hot-toast'

const sevColors: Record<string, string> = {
  critical: 'border-l-red-500 bg-red-50/50 dark:bg-red-950/20',
  high: 'border-l-orange-500 bg-orange-50/50 dark:bg-orange-950/20',
  medium: 'border-l-yellow-500 bg-yellow-50/30 dark:bg-yellow-950/10',
  low: 'border-l-blue-500',
  info: 'border-l-gray-400',
}

export function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [summary, setSummary] = useState<AlertSummary | null>(null)
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [sevFilter, setSevFilter] = useState('')
  const [categoryFilter, setCategoryFilter] = useState('')
  const pageSize = 20

  const fetchAlerts = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize }
      if (statusFilter) params.status = statusFilter
      if (sevFilter) params.severity = sevFilter
      if (categoryFilter) params.category = categoryFilter
      const [alertRes, sumRes] = await Promise.all([
        alertsApi.list(params),
        alertsApi.summary(),
      ])
      setAlerts(alertRes.data.items)
      setTotal(alertRes.data.total)
      setSummary(sumRes.data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchAlerts()
    const interval = setInterval(fetchAlerts, 30000)
    return () => clearInterval(interval)
  }, [page, statusFilter, sevFilter, categoryFilter])

  const handleMute = async (id: string) => {
    try {
      await alertsApi.mute(id, { duration_minutes: 60, reason: 'Mutado manualmente' })
      toast.success('Alerta mutado por 1 hora')
      fetchAlerts()
    } catch { toast.error('Erro') }
  }

  const handleUnmute = async (id: string) => {
    try { await alertsApi.unmute(id); toast.success('Alerta desmutado'); fetchAlerts() }
    catch { toast.error('Erro') }
  }

  const handleAcknowledge = async (id: string) => {
    try { await alertsApi.acknowledge(id); toast.success('Alerta reconhecido'); fetchAlerts() }
    catch { toast.error('Erro') }
  }

  const handleResolve = async (id: string) => {
    try { await alertsApi.resolve(id); toast.success('Alerta resolvido'); fetchAlerts() }
    catch { toast.error('Erro') }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-bold text-surface-900 dark:text-white">Alertas</h1>
        <p className="text-sm text-surface-500 mt-0.5">
          {summary?.total_active || 0} ativos · {summary?.critical || 0} críticos · {summary?.muted || 0} mutados
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {[
          { label: 'Ativos', value: summary?.total_active || 0, color: 'text-red-500' },
          { label: 'Críticos', value: summary?.critical || 0, color: 'text-red-600' },
          { label: 'Reconhecidos', value: summary?.acknowledged || 0, color: 'text-yellow-500' },
          { label: 'Mutados', value: summary?.muted || 0, color: 'text-surface-400' },
          { label: 'Dispositivos offline', value: summary?.device_offline || 0, color: 'text-red-500' },
          { label: 'Agentes offline', value: summary?.agent_offline || 0, color: 'text-red-600' },
        ].map((c) => (
          <div key={c.label} className="card-padded text-center">
            <p className={cn('text-2xl font-bold', c.color)}>{c.value}</p>
            <p className="text-xs text-surface-500">{c.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3">
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1) }} className="input w-auto py-1.5">
          <option value="">Todos os status</option>
          <option value="active">Ativos</option>
          <option value="acknowledged">Reconhecidos</option>
          <option value="muted">Mutados</option>
          <option value="resolved">Resolvidos</option>
        </select>
        <select value={sevFilter} onChange={(e) => { setSevFilter(e.target.value); setPage(1) }} className="input w-auto py-1.5">
          <option value="">Todas severidades</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
        <select value={categoryFilter} onChange={(e) => { setCategoryFilter(e.target.value); setPage(1) }} className="input w-auto py-1.5">
          <option value="">Todas as categorias</option>
          <option value="device_offline">Dispositivo offline</option>
          <option value="agent_offline">Agente offline</option>
          <option value="interface_errors">Erros de interface</option>
          <option value="vulnerability">Vulnerabilidades</option>
          <option value="new_device">Novos dispositivos</option>
        </select>
      </div>

      {/* Alert list */}
      <div className="space-y-2">
        {loading ? (
          <div className="card-padded text-center text-surface-400 py-12">Carregando...</div>
        ) : alerts.length === 0 ? (
          <div className="card-padded text-center py-12">
            <Bell className="w-10 h-10 mx-auto mb-3 text-green-500 opacity-60" />
            <p className="text-surface-500">Nenhum alerta encontrado</p>
          </div>
        ) : alerts.map((a) => (
          <div key={a.id} className={cn(
            'card border-l-4 px-5 py-3',
            sevColors[a.severity] || '',
            a.is_muted && 'opacity-60',
          )}>
            <div className="flex items-start gap-3">
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className={cn(
                    'badge text-2xs uppercase font-bold',
                    a.severity === 'critical' ? 'badge-critical' :
                    a.severity === 'high' ? 'badge-high' :
                    a.severity === 'medium' ? 'badge-medium' : 'badge-low',
                  )}>
                    {a.severity}
                  </span>
                  <span className="badge-info text-2xs">{a.category}</span>
                  {a.is_muted && <span className="badge bg-surface-200 text-surface-500 dark:bg-surface-700 text-2xs"><BellOff className="w-3 h-3" /> Mutado</span>}
                  {a.status === 'acknowledged' && <span className="badge bg-yellow-100 text-yellow-700 text-2xs"><Check className="w-3 h-3" /> Reconhecido</span>}
                  {a.status === 'resolved' && <span className="badge bg-green-100 text-green-700 text-2xs"><CheckCheck className="w-3 h-3" /> Resolvido</span>}
                </div>
                <p className="font-medium text-surface-900 dark:text-white mt-1">{a.title}</p>
                {a.message && <p className="text-sm text-surface-500 mt-0.5">{a.message}</p>}
                <div className="flex items-center gap-3 mt-1 text-xs text-surface-400">
                  <span>{formatDate(a.triggered_at)}</span>
                  {a.occurrence_count > 1 && <span>{a.occurrence_count}x ocorrências</span>}
                  {a.muted_until && <span>Mutado até {formatDate(a.muted_until)}</span>}
                </div>
                <div className="mt-2">
                  {a.category === 'agent_offline' && typeof a.details?.agent_id === 'string' && (
                    <Link to={`/agents/${a.details.agent_id}`} className="text-xs text-brand-600 hover:underline">Abrir detalhes do agente</Link>
                  )}
                  {a.device_id && a.category !== 'agent_offline' && (
                    <Link to={`/devices/${a.device_id}`} className="text-xs text-brand-600 hover:underline">Abrir detalhes do dispositivo</Link>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-1 shrink-0">
                {a.status === 'active' && (
                  <>
                    <button onClick={() => handleAcknowledge(a.id)} className="btn-ghost btn-sm" title="Reconhecer">
                      <Check className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleMute(a.id)} className="btn-ghost btn-sm" title="Mutar 1h">
                      <VolumeX className="w-4 h-4" />
                    </button>
                  </>
                )}
                {a.is_muted && (
                  <button onClick={() => handleUnmute(a.id)} className="btn-ghost btn-sm" title="Desmutar">
                    <Volume2 className="w-4 h-4" />
                  </button>
                )}
                {a.status !== 'resolved' && (
                  <button onClick={() => handleResolve(a.id)} className="btn-ghost btn-sm text-green-600" title="Resolver">
                    <CheckCheck className="w-4 h-4" />
                  </button>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary btn-sm">Anterior</button>
          <span className="text-sm text-surface-500">Página {page} de {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages} className="btn-secondary btn-sm">Próxima</button>
        </div>
      )}
    </div>
  )
}
