// netguard/frontend/src/pages/DevicesPage.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { devicesApi } from '@/services/api'
import type { Device } from '@/types'
import { cn, formatDate, deviceTypeLabel } from '@/lib/utils'
import {
  Network, Search, Pin, PinOff, EyeOff,
  ChevronRight, Wifi, WifiOff, Server, Monitor, Router, Printer,
  Radio, Phone, Camera, HelpCircle, Cpu,
  RefreshCw,
} from 'lucide-react'
import toast from 'react-hot-toast'

const typeIcons: Record<string, React.ElementType> = {
  switch: Router, router: Router, firewall: Network, server: Server,
  desktop: Monitor, printer: Printer, access_point: Radio,
  ip_phone: Phone, camera: Camera, iot: Cpu, unknown: HelpCircle,
}

function StatusDot({ status }: { status: string }) {
  return (
    <span className={cn('status-dot', status === 'online' ? 'status-online' : 'status-offline')} />
  )
}

function formatOpenPort(value: unknown): string {
  if (typeof value === 'number' || typeof value === 'string') return String(value)
  if (!value || typeof value !== 'object') return 'Porta desconhecida'
  const port = value as { port?: number | string; service?: string; name?: string; version?: string }
  return [port.port ?? '—', port.service || port.name, port.version]
    .filter((item) => item !== undefined && item !== null && item !== '')
    .join(' · ')
}

export function DevicesPage() {
  const [devices, setDevices] = useState<Device[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [typeFilter, setTypeFilter] = useState('')
  const [snmpFilter, setSnmpFilter] = useState<string>('')
  const [expanded, setExpanded] = useState<string | null>(null)
  const pageSize = 20

  const fetchDevices = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize, is_visible: true }
      if (search) params.search = search
      if (typeFilter) params.device_type = typeFilter
      if (snmpFilter !== '') params.snmp_enabled = snmpFilter === 'true'
      const { data } = await devicesApi.list(params)
      setDevices(data.items)
      setTotal(data.total)
    } catch { toast.error('Erro ao carregar dispositivos') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchDevices() }, [page, typeFilter, snmpFilter])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchDevices()
  }

  const handlePin = async (id: string) => {
    try {
      await devicesApi.pin(id)
      fetchDevices()
      toast.success('Dispositivo atualizado')
    } catch { toast.error('Erro') }
  }

  const handleHide = async (id: string) => {
    try {
      await devicesApi.delete(id)
      fetchDevices()
      toast.success('Dispositivo ocultado')
    } catch { toast.error('Erro') }
  }

  const totalPages = Math.ceil(total / pageSize)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Dispositivos</h1>
          <p className="text-sm text-surface-500 mt-0.5">{total} dispositivos encontrados</p>
        </div>
        <button onClick={fetchDevices} className="btn-secondary btn-sm">
          <RefreshCw className="w-4 h-4" /> Atualizar
        </button>
      </div>

      {/* Filters */}
      <div className="card-padded flex flex-wrap items-center gap-3">
        <form onSubmit={handleSearch} className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400" />
          <input type="text" placeholder="Buscar IP, hostname, fabricante..." value={search}
            onChange={(e) => setSearch(e.target.value)} className="input pl-10 py-1.5" />
        </form>
        <select value={typeFilter} onChange={(e) => { setTypeFilter(e.target.value); setPage(1) }}
          className="input w-auto py-1.5">
          <option value="">Todos os tipos</option>
          {['switch','router','firewall','server','desktop','printer','access_point','ip_phone','camera','iot','unknown'].map(t =>
            <option key={t} value={t}>{deviceTypeLabel(t)}</option>
          )}
        </select>
        <select value={snmpFilter} onChange={(e) => { setSnmpFilter(e.target.value); setPage(1) }}
          className="input w-auto py-1.5">
          <option value="">SNMP: Todos</option>
          <option value="true">Com SNMP</option>
          <option value="false">Sem SNMP</option>
        </select>
      </div>

      {/* Device list */}
      <div className="space-y-2">
        {loading ? (
          <div className="card-padded text-center text-surface-400 py-12">Carregando...</div>
        ) : devices.length === 0 ? (
          <div className="card-padded text-center text-surface-400 py-12">
            <Network className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>Nenhum dispositivo encontrado</p>
            <p className="text-xs mt-1">Execute um Discovery Scan para encontrar dispositivos</p>
          </div>
        ) : devices.map((d) => {
          const Icon = typeIcons[d.device_type] || HelpCircle
          const isExpanded = expanded === d.id

          return (
            <div key={d.id} className="card overflow-hidden">
              {/* Summary row */}
              <button onClick={() => setExpanded(isExpanded ? null : d.id)}
                className="w-full flex items-center gap-4 px-5 py-3 hover:bg-surface-50 dark:hover:bg-surface-800/50 transition-colors text-left">
                <ChevronRight className={cn('w-4 h-4 text-surface-400 shrink-0 transition-transform', isExpanded && 'rotate-90')} />
                <StatusDot status={d.status} />
                <Icon className="w-5 h-5 text-surface-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-sm font-medium text-surface-900 dark:text-white">{d.ip_address}</span>
                    {d.hostname && <span className="text-sm text-surface-500 truncate">({d.hostname})</span>}
                    {d.is_pinned && <Pin className="w-3 h-3 text-brand-500" />}
                  </div>
                  <div className="flex items-center gap-3 mt-0.5">
                    <span className="text-xs text-surface-400">{deviceTypeLabel(d.device_type)}</span>
                    {d.vendor && <span className="text-xs text-surface-400">· {d.vendor}</span>}
                    {d.os_name && <span className="text-xs text-surface-400">· {d.os_name}</span>}
                  </div>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  {d.snmp_enabled
                    ? <span className="badge bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"><Wifi className="w-3 h-3" /> SNMP</span>
                    : <span className="badge bg-surface-100 text-surface-500 dark:bg-surface-700"><WifiOff className="w-3 h-3" /> Sem SNMP</span>
                  }
                  <span className="text-xs text-surface-400">{formatDate(d.last_seen)}</span>
                </div>
              </button>

              {/* Expanded details */}
              {isExpanded && (
                <div className="border-t border-surface-200 dark:border-surface-700 px-5 py-4 bg-surface-50/50 dark:bg-surface-800/30">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div><span className="label">MAC</span><p className="font-mono text-surface-700 dark:text-surface-300">{d.mac_address || '—'}</p></div>
                    <div><span className="label">Modelo</span><p className="text-surface-700 dark:text-surface-300">{d.model || '—'}</p></div>
                    <div><span className="label">SO</span><p className="text-surface-700 dark:text-surface-300">{d.os_name ? `${d.os_name} ${d.os_version || ''}` : '—'}</p></div>
                    <div><span className="label">Segmento</span><p className="text-surface-700 dark:text-surface-300">{d.network_segment || '—'}</p></div>
                    {d.snmp_enabled && <>
                      <div><span className="label">SNMP Name</span><p className="text-surface-700 dark:text-surface-300">{d.snmp_sys_name || '—'}</p></div>
                      <div><span className="label">SNMP Location</span><p className="text-surface-700 dark:text-surface-300">{d.snmp_sys_location || '—'}</p></div>
                      <div><span className="label">Uptime</span><p className="text-surface-700 dark:text-surface-300">{d.snmp_sys_uptime || '—'}</p></div>
                    </>}
                    {d.cpu_usage != null && (
                      <div><span className="label">CPU</span><p className="text-surface-700 dark:text-surface-300">{d.cpu_usage.toFixed(1)}%</p></div>
                    )}
                    {d.memory_usage != null && (
                      <div><span className="label">Memória</span><p className="text-surface-700 dark:text-surface-300">{d.memory_usage.toFixed(1)}%</p></div>
                    )}
                    <div><span className="label">Primeira vez visto</span><p className="text-surface-700 dark:text-surface-300">{formatDate(d.first_seen)}</p></div>
                    {d.open_ports && d.open_ports.length > 0 && (
                      <div className="col-span-2"><span className="label">Portas abertas</span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {d.open_ports.slice(0, 20).map((p, i) => (
                            <span key={i} className="badge-info text-2xs font-mono">{formatOpenPort(p)}</span>
                          ))}
                        </div>
                      </div>
                    )}
                    {d.tags.length > 0 && (
                      <div className="col-span-2"><span className="label">Tags</span>
                        <div className="flex gap-1 mt-1">
                          {d.tags.map((t, i) => <span key={i} className="badge bg-brand-100 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400">{t}</span>)}
                        </div>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-2 mt-4 pt-3 border-t border-surface-200 dark:border-surface-700">
                    <Link to={`/devices/${d.id}`} className="btn-primary btn-sm">Detalhes e gráficos</Link>
                    <button onClick={() => handlePin(d.id)} className="btn-ghost btn-sm">
                      {d.is_pinned ? <><PinOff className="w-3.5 h-3.5" /> Desfixar</> : <><Pin className="w-3.5 h-3.5" /> Fixar</>}
                    </button>
                    <button onClick={() => handleHide(d.id)} className="btn-ghost btn-sm text-red-500 hover:text-red-600">
                      <EyeOff className="w-3.5 h-3.5" /> Ocultar
                    </button>
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
            className="btn-secondary btn-sm">Anterior</button>
          <span className="text-sm text-surface-500">Página {page} de {totalPages}</span>
          <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
            className="btn-secondary btn-sm">Próxima</button>
        </div>
      )}
    </div>
  )
}
