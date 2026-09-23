import { useCallback, useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import {
  Activity, AlertTriangle, ChevronDown, ChevronRight, Database,
  Plus, RefreshCw, Search, Server, Trash2, X,
} from 'lucide-react'

import api from '@/services/api'
import { cn, formatDate } from '@/lib/utils'

interface LogEvent {
  id: string
  received_at: string
  event_at?: string
  source_ip: string
  source_port?: number
  protocol: string
  facility: string
  severity: string
  severity_num?: number
  hostname?: string
  app_name?: string
  proc_id?: string
  msg_id?: string
  message: string
  raw: string
  properties: Record<string, unknown>
  security_category?: string
}

interface LogStats {
  total_messages: number
  rate_5m: number
  security_events: number
  by_severity: Record<string, number>
  by_source: Record<string, number>
  by_facility: Record<string, number>
  receiver: {
    running: boolean
    port: number
    udp: boolean
    tcp: boolean
    last_error?: string
    received_count?: number
    persisted_count?: number
    failed_count?: number
    last_received_at?: string
    last_persisted_at?: string
    last_source?: string
  }
}

interface LogFacets {
  severities: string[]
  facilities: string[]
  hosts: string[]
  sources: string[]
  applications: string[]
  protocols: string[]
}

interface LogMetric {
  id: string
  name: string
  description?: string
  filters: Record<string, unknown>
  window_minutes: number
  threshold: number
  minimum_span_seconds: number
  threshold_operator: string
  severity: string
  is_active: boolean
  current_value: number
  last_evaluated_at?: string
  last_triggered_at?: string
  cooldown_minutes: number
  notify_email: boolean
  notify_webhook: boolean
}

interface Filters {
  q: string
  match: 'all' | 'any'
  severity: string
  facility: string
  host: string
  app_name: string
  protocol: string
  property_key: string
  property_value: string
  period: string
}

const emptyFilters: Filters = {
  q: '', match: 'all', severity: '', facility: '', host: '', app_name: '',
  protocol: '', property_key: '', property_value: '', period: '60',
}

const severityStyle: Record<string, string> = {
  emergency: 'text-red-700 bg-red-100 dark:bg-red-950/40',
  alert: 'text-red-600 bg-red-100 dark:bg-red-950/40',
  critical: 'text-red-500 bg-red-50 dark:bg-red-950/30',
  error: 'text-orange-600 bg-orange-50 dark:bg-orange-950/30',
  warning: 'text-yellow-700 bg-yellow-50 dark:bg-yellow-950/30',
  notice: 'text-blue-600 bg-blue-50 dark:bg-blue-950/30',
  informational: 'text-surface-600 bg-surface-100 dark:bg-surface-700',
  debug: 'text-surface-500 bg-surface-50 dark:bg-surface-800',
}

function periodStart(period: string): string | undefined {
  if (!period) return undefined
  return new Date(Date.now() - Number(period) * 60_000).toISOString()
}

export function SyslogPage() {
  const [tab, setTab] = useState<'events' | 'metrics'>('events')
  const [events, setEvents] = useState<LogEvent[]>([])
  const [total, setTotal] = useState(0)
  const [stats, setStats] = useState<LogStats | null>(null)
  const [ingestion, setIngestion] = useState<Record<string, { total: number; last_5m: number; last_persisted_at?: string }> | null>(null)
  const [facets, setFacets] = useState<LogFacets | null>(null)
  const [metrics, setMetrics] = useState<LogMetric[]>([])
  const [filters, setFilters] = useState<Filters>(emptyFilters)
  const [appliedFilters, setAppliedFilters] = useState<Filters>(emptyFilters)
  const [loading, setLoading] = useState(true)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [expanded, setExpanded] = useState<string | null>(null)
  const [showMetric, setShowMetric] = useState(false)
  const [metricName, setMetricName] = useState('')
  const [metricThreshold, setMetricThreshold] = useState(10)
  const [metricSeverity, setMetricSeverity] = useState('medium')
  const [metricCooldown, setMetricCooldown] = useState(15)
  const [notifyEmail, setNotifyEmail] = useState(false)
  const [saving, setSaving] = useState(false)

  const requestParams = useCallback((value: Filters) => {
    const params: Record<string, string | number> = { page_size: 200, match: value.match }
    for (const key of ['q', 'severity', 'facility', 'host', 'app_name', 'protocol', 'property_key', 'property_value'] as const) {
      if (value[key]) params[key] = value[key]
    }
    const start = periodStart(value.period)
    if (start) params.from_time = start
    return params
  }, [])

  const loadEvents = useCallback(async (value: Filters = appliedFilters) => {
    setLoading(true)
    try {
      const period = Number(value.period || 1440)
      const [eventRes, statsRes, facetRes, ingestionRes] = await Promise.all([
        api.get('/logs/events', { params: requestParams(value) }),
        api.get('/logs/stats', { params: { minutes: period } }),
        api.get('/logs/facets'),
        api.get('/logs/ingestion/health'),
      ])
      setEvents(eventRes.data.items)
      setTotal(eventRes.data.total)
      setStats(statsRes.data)
      setFacets(facetRes.data)
      setIngestion(ingestionRes.data)
    } catch {
      toast.error('Não foi possível consultar os logs')
    } finally {
      setLoading(false)
    }
  }, [appliedFilters, requestParams])

  const loadMetrics = useCallback(async () => {
    try {
      const response = await api.get('/logs/metrics')
      setMetrics(response.data)
    } catch {
      toast.error('Não foi possível carregar as métricas de logs')
    }
  }, [])

  useEffect(() => { loadEvents(); loadMetrics() }, [loadEvents, loadMetrics])
  useEffect(() => {
    if (!autoRefresh) return
    const timer = window.setInterval(() => {
      if (tab === 'events') loadEvents()
      else loadMetrics()
    }, 5000)
    return () => window.clearInterval(timer)
  }, [autoRefresh, loadEvents, loadMetrics, tab])

  const applySearch = () => {
    setAppliedFilters(filters)
    loadEvents(filters)
  }

  const metricFilters = () => {
    const result: Record<string, unknown> = { match: appliedFilters.match }
    for (const key of ['q', 'severity', 'facility', 'host', 'app_name', 'protocol', 'property_key', 'property_value'] as const) {
      if (appliedFilters[key]) result[key] = appliedFilters[key]
    }
    return result
  }

  const createMetric = async () => {
    if (metricName.trim().length < 3) {
      toast.error('Informe um nome com pelo menos 3 caracteres')
      return
    }
    setSaving(true)
    try {
      await api.post('/logs/metrics', {
        name: metricName.trim(),
        filters: metricFilters(),
        window_minutes: 5,
        threshold: metricThreshold,
        minimum_span_seconds: 180,
        threshold_operator: '>=',
        severity: metricSeverity,
        cooldown_minutes: metricCooldown,
        notify_email: notifyEmail,
      })
      toast.success('Métrica criada e monitoramento ativado')
      setShowMetric(false)
      setMetricName('')
      await loadMetrics()
      setTab('metrics')
    } catch (error: unknown) {
      const message = (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
      toast.error(message || 'Não foi possível criar a métrica')
    } finally {
      setSaving(false)
    }
  }

  const toggleMetric = async (metric: LogMetric) => {
    try {
      await api.put(`/logs/metrics/${metric.id}`, { is_active: !metric.is_active })
      await loadMetrics()
    } catch { toast.error('Não foi possível alterar a métrica') }
  }

  const evaluateMetric = async (metric: LogMetric) => {
    try {
      await api.post(`/logs/metrics/${metric.id}/evaluate`)
      await loadMetrics()
      toast.success('Métrica recalculada')
    } catch { toast.error('Falha ao recalcular a métrica') }
  }

  const deleteMetric = async (metric: LogMetric) => {
    if (!window.confirm(`Excluir a métrica “${metric.name}” e sua regra de alerta?`)) return
    try {
      await api.delete(`/logs/metrics/${metric.id}`)
      await loadMetrics()
      toast.success('Métrica excluída')
    } catch { toast.error('Não foi possível excluir a métrica') }
  }

  const testPersistence = async () => { try { const response = await api.post('/logs/receiver/test'); toast.success(`Persistência confirmada: ${response.data.event_id}`); await loadEvents() } catch { toast.error('O teste de persistência falhou; consulte o erro da API') } }

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Logs</h1>
          <p className="text-sm text-surface-500 mt-0.5">
            Syslog UDP/TCP · pesquisa, métricas e alertas por ocorrência
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={cn('badge', stats?.receiver.running ? 'badge-low' : 'badge-critical')}>
            <span className={stats?.receiver.running ? 'status-online' : 'status-offline'} />
            Porta {stats?.receiver.port || 514} · UDP {stats?.receiver.udp ? 'OK' : 'OFF'} · TCP {stats?.receiver.tcp ? 'OK' : 'OFF'}
          </span>
          <label className="flex items-center gap-2 text-xs text-surface-500">
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)} />
            Atualização automática
          </label>
          <button onClick={() => tab === 'events' ? loadEvents() : loadMetrics()} className="btn-secondary btn-sm" title="Atualizar">
            <RefreshCw className="w-4 h-4" />
          </button>
          <button onClick={testPersistence} className="btn-secondary btn-sm">Testar persistência</button>
        </div>
      </div>

      <div className="flex gap-1 border-b border-surface-200 dark:border-surface-700">
        <button onClick={() => setTab('events')} className={cn('px-4 py-2 text-sm font-medium border-b-2', tab === 'events' ? 'border-brand-600 text-brand-600' : 'border-transparent text-surface-500')}>Eventos</button>
        <button onClick={() => setTab('metrics')} className={cn('px-4 py-2 text-sm font-medium border-b-2', tab === 'metrics' ? 'border-brand-600 text-brand-600' : 'border-transparent text-surface-500')}>Métricas ({metrics.length})</button>
      </div>

      {tab === 'events' ? <>
        {stats && <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <Stat icon={Database} label="Eventos no período" value={stats.total_messages} />
          <Stat icon={Activity} label="Últimos 5 minutos" value={stats.rate_5m} color="text-brand-600" />
          <Stat icon={Server} label="Fontes" value={Object.keys(stats.by_source).length} />
          <Stat icon={AlertTriangle} label="Eventos de segurança" value={stats.security_events} color="text-red-500" />
        </div>}
        {stats && <div className="card-padded text-xs flex flex-wrap gap-x-6 gap-y-1 text-surface-500"><span>Recebidos neste processo: <b>{stats.receiver.received_count || 0}</b></span><span>Persistidos: <b>{stats.receiver.persisted_count || 0}</b></span><span>Falhas: <b className={stats.receiver.failed_count ? 'text-red-500' : ''}>{stats.receiver.failed_count || 0}</b></span><span>Última origem: <b>{stats.receiver.last_source || 'nenhuma'}</b></span><span>Última gravação: <b>{stats.receiver.last_persisted_at ? formatDate(stats.receiver.last_persisted_at) : 'nenhuma'}</b></span>{stats.receiver.last_error && <span className="text-red-500">Erro: {stats.receiver.last_error}</span>}</div>}
        {ingestion && <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">{([['syslog', 'Syslog'], ['agent_metrics', 'Métricas de agente'], ['device_metrics', 'Métricas SNMP'], ['snmp_collections', 'Execuções SNMP']] as const).map(([key, label]) => <div className="card-padded" key={key}><p className="text-xs text-surface-500">{label} no banco</p><p className="text-xl font-bold">{ingestion[key]?.total || 0}</p><p className="text-xs text-surface-400">últimos 5 min: {ingestion[key]?.last_5m || 0} · {ingestion[key]?.last_persisted_at ? formatDate(ingestion[key].last_persisted_at!) : 'sem gravação'}</p></div>)}</div>}

        <div className="card-padded space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            <div className="xl:col-span-2">
              <label className="label">Termos ou contexto da mensagem</label>
              <div className="relative">
                <Search className="absolute left-3 top-2.5 w-4 h-4 text-surface-400" />
                <input value={filters.q} onChange={e => setFilters({ ...filters, q: e.target.value })} onKeyDown={e => e.key === 'Enter' && applySearch()} className="input pl-9" placeholder={'Ex.: "failed password" firewall blocked'} />
              </div>
            </div>
            <FilterSelect label="Correspondência" value={filters.match} onChange={value => setFilters({ ...filters, match: value as 'all' | 'any' })} options={[['all', 'Todos os termos'], ['any', 'Qualquer termo']]} />
            <FilterSelect label="Período" value={filters.period} onChange={value => setFilters({ ...filters, period: value })} options={[['5', 'Últimos 5 minutos'], ['15', 'Últimos 15 minutos'], ['60', 'Última hora'], ['360', 'Últimas 6 horas'], ['1440', 'Últimas 24 horas'], ['10080', 'Últimos 7 dias']]} />
            <FilterSelect label="Nível" value={filters.severity} onChange={value => setFilters({ ...filters, severity: value })} options={(facets?.severities || []).map(value => [value, value])} empty="Todos os níveis" />
            <FilterSelect label="Facility" value={filters.facility} onChange={value => setFilters({ ...filters, facility: value })} options={(facets?.facilities || []).map(value => [value, value])} empty="Todas" />
            <div><label className="label">Host ou IP</label><input className="input" value={filters.host} onChange={e => setFilters({ ...filters, host: e.target.value })} placeholder="hostname ou 192.168..." /></div>
            <FilterSelect label="Aplicação" value={filters.app_name} onChange={value => setFilters({ ...filters, app_name: value })} options={(facets?.applications || []).map(value => [value, value])} empty="Todas" />
            <FilterSelect label="Protocolo" value={filters.protocol} onChange={value => setFilters({ ...filters, protocol: value })} options={(facets?.protocols || ['udp', 'tcp']).map(value => [value, value.toUpperCase()])} empty="UDP e TCP" />
            <div><label className="label">Propriedade</label><input className="input" value={filters.property_key} onChange={e => setFilters({ ...filters, property_key: e.target.value })} placeholder="user, event_id, transport..." /></div>
            <div><label className="label">Valor da propriedade</label><input className="input" value={filters.property_value} onChange={e => setFilters({ ...filters, property_value: e.target.value })} placeholder="contém..." /></div>
          </div>
          <div className="flex flex-wrap justify-between gap-2 pt-1">
            <div className="text-xs text-surface-500 self-center">{total} ocorrência(s) encontradas · exibindo até 200</div>
            <div className="flex gap-2">
              <button className="btn-ghost btn-sm" onClick={() => { setFilters(emptyFilters); setAppliedFilters(emptyFilters); loadEvents(emptyFilters) }}><X className="w-4 h-4" /> Limpar</button>
              <button className="btn-secondary btn-sm" onClick={() => setShowMetric(true)}><Plus className="w-4 h-4" /> Criar métrica desta pesquisa</button>
              <button className="btn-primary btn-sm" onClick={applySearch}><Search className="w-4 h-4" /> Pesquisar</button>
            </div>
          </div>
        </div>

        <div className="card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-surface-50 dark:bg-surface-800 text-surface-500 text-left">
                <tr><th className="w-8 p-3" /><th className="p-3">Horário</th><th className="p-3">Nível</th><th className="p-3">Host / IP</th><th className="p-3">Aplicação</th><th className="p-3">Mensagem</th></tr>
              </thead>
              <tbody className="divide-y divide-surface-100 dark:divide-surface-800">
                {loading ? <tr><td colSpan={6} className="text-center py-12 text-surface-400">Carregando...</td></tr> : events.length === 0 ? <tr><td colSpan={6} className="text-center py-12 text-surface-400">Nenhum log encontrado para os filtros informados.</td></tr> : events.map(event => <LogRow key={event.id} event={event} expanded={expanded === event.id} onToggle={() => setExpanded(expanded === event.id ? null : event.id)} />)}
              </tbody>
            </table>
          </div>
        </div>
      </> : <div className="space-y-3">
        <div className="flex items-center justify-between"><p className="text-sm text-surface-500">Cada métrica conta os eventos que correspondem à consulta dentro de uma janela móvel e gera alertas automaticamente.</p><button className="btn-primary btn-sm" onClick={() => { setTab('events'); setShowMetric(true) }}><Plus className="w-4 h-4" /> Nova métrica</button></div>
        {metrics.length === 0 ? <div className="card-padded text-center py-12 text-surface-400">Nenhuma métrica de logs criada.</div> : metrics.map(metric => <div key={metric.id} className="card-padded flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2"><span className={metric.is_active ? 'status-online' : 'status-offline'} /><h3 className="font-semibold text-surface-900 dark:text-white">{metric.name}</h3><span className={cn('badge', metric.severity === 'critical' ? 'badge-critical' : metric.severity === 'high' ? 'badge-high' : 'badge-medium')}>{metric.severity}</span></div>
            <p className="mt-1 text-xs text-surface-500">{JSON.stringify(metric.filters)} · janela {metric.window_minutes} min · alerta quando valor {metric.threshold_operator} {metric.threshold} e duração ≥ {metric.minimum_span_seconds}s</p>
            <p className="mt-1 text-xs text-surface-400">Última avaliação: {metric.last_evaluated_at ? formatDate(metric.last_evaluated_at) : 'ainda não avaliada'}{metric.last_triggered_at ? ` · último alerta: ${formatDate(metric.last_triggered_at)}` : ''}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <div className="text-center px-4"><p className={cn('text-2xl font-bold', metric.current_value >= metric.threshold ? 'text-red-500' : 'text-surface-900 dark:text-white')}>{metric.current_value}</p><p className="text-2xs text-surface-500">valor atual</p></div>
            <button className="btn-secondary btn-sm" onClick={() => evaluateMetric(metric)}>Avaliar</button>
            <button className="btn-secondary btn-sm" onClick={() => toggleMetric(metric)}>{metric.is_active ? 'Pausar' : 'Ativar'}</button>
            <button className="btn-ghost btn-sm text-red-500" onClick={() => deleteMetric(metric)} title="Excluir"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>)}
      </div>}

      {showMetric && <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4"><div className="card-padded w-full max-w-lg shadow-xl">
        <div className="flex items-center justify-between mb-4"><div><h2 className="font-semibold text-surface-900 dark:text-white">Criar métrica da pesquisa</h2><p className="text-xs text-surface-500 mt-1">A regra será avaliada a cada minuto e aparecerá em Alertas.</p></div><button className="btn-ghost btn-sm" onClick={() => setShowMetric(false)}><X className="w-4 h-4" /></button></div>
        <div className="space-y-3">
          <div><label className="label">Nome da métrica</label><input autoFocus className="input" value={metricName} onChange={e => setMetricName(e.target.value)} placeholder="Ex.: Falhas de login SSH" /></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="label">Alertar a partir de</label><input type="number" min={1} className="input" value={metricThreshold} onChange={e => setMetricThreshold(Number(e.target.value))} /></div><FilterSelect label="Severidade do alerta" value={metricSeverity} onChange={setMetricSeverity} options={['low', 'medium', 'high', 'critical'].map(value => [value, value])} /></div>
          <div className="grid grid-cols-2 gap-3"><div><label className="label">Regra temporal</label><input className="input bg-surface-50 dark:bg-surface-900" readOnly value="5 min / duração mínima 3 min" /></div><div><label className="label">Cooldown (minutos)</label><input type="number" min={1} className="input" value={metricCooldown} onChange={e => setMetricCooldown(Number(e.target.value))} /></div></div>
          <label className="flex items-center gap-2 text-sm text-surface-600 dark:text-surface-300"><input type="checkbox" checked={notifyEmail} onChange={e => setNotifyEmail(e.target.checked)} /> Enviar e-mail quando o alerta for criado</label>
          <div className="rounded-lg bg-surface-50 dark:bg-surface-900 p-3 text-xs text-surface-500 break-all"><strong>Consulta:</strong> {JSON.stringify(metricFilters())}</div>
        </div>
        <div className="flex justify-end gap-2 mt-5"><button className="btn-secondary" onClick={() => setShowMetric(false)}>Cancelar</button><button className="btn-primary" disabled={saving} onClick={createMetric}>{saving ? 'Salvando...' : 'Criar e monitorar'}</button></div>
      </div></div>}
    </div>
  )
}

function Stat({ icon: Icon, label, value, color = 'text-surface-900 dark:text-white' }: { icon: typeof Activity; label: string; value: number; color?: string }) {
  return <div className="card-padded flex items-center gap-3"><div className="w-9 h-9 rounded-lg bg-surface-100 dark:bg-surface-700 flex items-center justify-center"><Icon className="w-4 h-4 text-surface-500" /></div><div><p className={cn('text-xl font-bold', color)}>{value}</p><p className="text-xs text-surface-500">{label}</p></div></div>
}

function FilterSelect({ label, value, onChange, options, empty }: { label: string; value: string; onChange: (value: string) => void; options: string[][]; empty?: string }) {
  return <div><label className="label">{label}</label><select className="input" value={value} onChange={e => onChange(e.target.value)}>{empty !== undefined && <option value="">{empty}</option>}{options.map(([key, text]) => <option key={key} value={key}>{text}</option>)}</select></div>
}

function LogRow({ event, expanded, onToggle }: { event: LogEvent; expanded: boolean; onToggle: () => void }) {
  return <>
    <tr className={cn('hover:bg-surface-50 dark:hover:bg-surface-800/40 cursor-pointer', event.security_category && 'bg-red-50/40 dark:bg-red-950/10')} onClick={onToggle}>
      <td className="p-3 text-surface-400">{expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</td>
      <td className="p-3 whitespace-nowrap text-surface-500">{formatDate(event.received_at)}</td>
      <td className="p-3"><span className={cn('px-2 py-1 rounded text-2xs uppercase font-semibold', severityStyle[event.severity] || severityStyle.informational)}>{event.severity}</span></td>
      <td className="p-3"><p className="text-surface-800 dark:text-surface-200">{event.hostname || event.source_ip}</p><p className="text-2xs text-surface-400">{event.source_ip} · {event.protocol.toUpperCase()}</p></td>
      <td className="p-3 text-brand-600 dark:text-brand-400">{event.app_name || event.facility}</td>
      <td className="p-3 max-w-xl"><p className="truncate text-surface-700 dark:text-surface-300">{event.message}</p>{event.security_category && <span className="badge-critical text-2xs mt-1">{event.security_category}</span>}</td>
    </tr>
    {expanded && <tr><td colSpan={6} className="p-4 bg-surface-50 dark:bg-surface-900"><div className="grid md:grid-cols-2 gap-4 text-xs"><div><p className="font-semibold mb-2 text-surface-700 dark:text-surface-200">Mensagem original</p><pre className="whitespace-pre-wrap break-all rounded bg-surface-900 text-surface-200 p-3 max-h-48 overflow-auto">{event.raw}</pre></div><div><p className="font-semibold mb-2 text-surface-700 dark:text-surface-200">Propriedades</p><pre className="whitespace-pre-wrap break-all rounded bg-surface-100 dark:bg-surface-800 text-surface-700 dark:text-surface-300 p-3 max-h-48 overflow-auto">{JSON.stringify({ facility: event.facility, source_port: event.source_port, proc_id: event.proc_id, msg_id: event.msg_id, ...event.properties }, null, 2)}</pre></div></div></td></tr>}
  </>
}
