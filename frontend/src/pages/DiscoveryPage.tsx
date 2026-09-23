import { useEffect, useState } from 'react'
import { scansApi } from '@/services/api'
import type { ScanJob } from '@/types'
import { TaskDetailsModal } from '@/components/scans/TaskDetailsModal'
import { cn, formatDate } from '@/lib/utils'
import { Radar, Play, XCircle, Clock, CheckCircle2, AlertCircle, Loader2, ServerCog, CalendarClock } from 'lucide-react'
import toast from 'react-hot-toast'

interface ExecutorHealth {
  status: 'online' | 'offline'
  workers: string[]
  message: string
}

const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-yellow-500', label: 'Pendente' },
  running: { icon: Loader2, color: 'text-brand-500 animate-spin', label: 'Executando' },
  completed: { icon: CheckCircle2, color: 'text-green-500', label: 'Concluído' },
  failed: { icon: AlertCircle, color: 'text-red-500', label: 'Falhou' },
  cancelled: { icon: XCircle, color: 'text-surface-400', label: 'Cancelado' },
}

const weekdays = [
  { value: 0, label: 'Seg' }, { value: 1, label: 'Ter' },
  { value: 2, label: 'Qua' }, { value: 3, label: 'Qui' },
  { value: 4, label: 'Sex' }, { value: 5, label: 'Sáb' },
  { value: 6, label: 'Dom' },
]

const initialForm = {
  name: '', target: '', profile: 'quick', isScheduled: false,
  scheduleFrequency: 'daily', scheduleTime: '02:00',
  scheduleDays: [0], scheduleDayOfMonth: 1,
}

export function DiscoveryPage() {
  const [scans, setScans] = useState<ScanJob[]>([])
  const [selected, setSelected] = useState<ScanJob | null>(null)
  const [executor, setExecutor] = useState<ExecutorHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [formData, setFormData] = useState(initialForm)
  const [submitting, setSubmitting] = useState(false)

  const fetchScans = async () => {
    try {
      const { data } = await scansApi.list({ scan_type: 'discovery', page_size: 50 })
      setScans(data.items)
      setSelected((current) => current ? data.items.find((item: ScanJob) => item.id === current.id) || current : null)
    } catch { /* mantém o estado anterior */ }
    finally { setLoading(false) }
  }

  const fetchExecutor = async () => {
    try { const { data } = await scansApi.executorHealth(); setExecutor(data) }
    catch { setExecutor({ status: 'offline', workers: [], message: 'Não foi possível consultar o executor' }) }
  }

  useEffect(() => {
    fetchScans(); fetchExecutor()
    const scanInterval = setInterval(fetchScans, 2500)
    const healthInterval = setInterval(fetchExecutor, 15000)
    return () => { clearInterval(scanInterval); clearInterval(healthInterval) }
  }, [])

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault()
    if (!formData.name || !formData.target) return
    if (executor?.status === 'offline') { toast.error('O executor de scans está offline'); return }
    setSubmitting(true)
    try {
      const { data } = await scansApi.create({
        name: formData.name,
        target: formData.target,
        scan_type: 'discovery',
        options: { profile: formData.profile },
        is_scheduled: formData.isScheduled,
        schedule_frequency: formData.isScheduled ? formData.scheduleFrequency : undefined,
        schedule_time: formData.scheduleTime,
        schedule_days: formData.scheduleDays,
        schedule_day_of_month: formData.scheduleDayOfMonth,
      })
      toast.success(formData.isScheduled ? 'Discovery iniciado e agendamento ativado' : 'Discovery enviado para execução')
      setShowForm(false)
      setFormData(initialForm)
      setSelected(data)
      fetchScans()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Erro ao criar discovery')
      fetchExecutor()
    } finally { setSubmitting(false) }
  }

  const handleCancel = async (id: string) => {
    try { await scansApi.cancel(id); toast.success('Cancelamento solicitado'); fetchScans() }
    catch { toast.error('Não foi possível cancelar') }
  }

  const handleDisableSchedule = async (id: string) => {
    try { await scansApi.disableSchedule(id); toast.success('Agendamento desativado'); fetchScans() }
    catch { toast.error('Não foi possível desativar o agendamento') }
  }

  const toggleScheduleDay = (day: number) => {
    setFormData((value) => ({
      ...value,
      scheduleDays: value.scheduleDays.includes(day)
        ? value.scheduleDays.filter((item) => item !== day)
        : [...value.scheduleDays, day].sort(),
    }))
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Network Discovery</h1>
          <p className="text-sm text-surface-500 mt-0.5">Descoberta de dispositivos com acompanhamento em tempo real</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary" disabled={executor?.status === 'offline'}>
          <Play className="w-4 h-4" /> Novo Discovery
        </button>
      </div>

      <div className={cn('card-padded flex items-center gap-3 border-l-4', executor?.status === 'online' ? 'border-l-green-500' : executor?.status === 'offline' ? 'border-l-red-500' : 'border-l-yellow-500')}>
        <ServerCog className={cn('w-5 h-5', executor?.status === 'online' ? 'text-green-500' : executor?.status === 'offline' ? 'text-red-500' : 'text-yellow-500')} />
        <div className="flex-1">
          <p className="text-sm font-medium">Executor de scans: {executor?.status === 'online' ? 'online' : executor?.status === 'offline' ? 'offline' : 'verificando'}</p>
          <p className="text-xs text-surface-500">{executor?.message || 'Consultando workers Celery...'}</p>
        </div>
        {executor?.status === 'offline' && <button className="btn-secondary btn-sm" onClick={fetchExecutor}>Verificar novamente</button>}
      </div>

      {executor?.status === 'offline' && (
        <div className="rounded-lg bg-red-50 dark:bg-red-950/20 border border-red-200 dark:border-red-900 p-3 text-xs text-red-700 dark:text-red-300">
          Nenhum scan será executado até o worker Celery estar ativo e consumindo a fila <code>scans</code>.
        </div>
      )}

      {showForm && (
        <form onSubmit={handleSubmit} className="card-padded space-y-4">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Configurar discovery</h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div><label className="label">Nome</label><input className="input" placeholder="Ex: Rede administrativa" value={formData.name} onChange={(event) => setFormData((value) => ({ ...value, name: event.target.value }))} required /></div>
            <div><label className="label">Alvo (IP, CIDR ou range)</label><input className="input font-mono" placeholder="192.168.0.0/24" value={formData.target} onChange={(event) => setFormData((value) => ({ ...value, target: event.target.value.trim() }))} required /></div>
            <div>
              <label className="label">Perfil</label>
              <select className="input" value={formData.profile} onChange={(event) => setFormData((value) => ({ ...value, profile: event.target.value }))}>
                <option value="quick">Rápido — descoberta de hosts</option>
                <option value="detailed">Detalhado — SO e 100 portas</option>
                <option value="no_ping">Sem ping — hosts que bloqueiam ICMP</option>
              </select>
            </div>
          </div>
          <div className="rounded-lg border border-surface-200 dark:border-surface-700 p-4 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input type="checkbox" checked={formData.isScheduled} onChange={(event) => setFormData((value) => ({ ...value, isScheduled: event.target.checked }))} />
              <CalendarClock className="w-4 h-4 text-brand-500" /> Agendar novas execuções
            </label>
            {formData.isScheduled && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div><label className="label">Frequência</label><select className="input" value={formData.scheduleFrequency} onChange={(event) => setFormData((value) => ({ ...value, scheduleFrequency: event.target.value }))}><option value="daily">Diário</option><option value="weekly">Semanal</option><option value="biweekly">Quinzenal</option><option value="monthly">Mensal</option><option value="custom">Dias personalizados</option></select></div>
                <div><label className="label">Horário</label><input type="time" className="input" value={formData.scheduleTime} onChange={(event) => setFormData((value) => ({ ...value, scheduleTime: event.target.value }))} required /></div>
                {formData.scheduleFrequency === 'monthly' && <div><label className="label">Dia do mês</label><input type="number" min={1} max={28} className="input" value={formData.scheduleDayOfMonth} onChange={(event) => setFormData((value) => ({ ...value, scheduleDayOfMonth: Number(event.target.value) }))} /></div>}
                {formData.scheduleFrequency === 'weekly' && <div><label className="label">Dia da semana</label><select className="input" value={formData.scheduleDays[0] ?? 0} onChange={(event) => setFormData((value) => ({ ...value, scheduleDays: [Number(event.target.value)] }))}>{weekdays.map((day) => <option key={day.value} value={day.value}>{day.label}</option>)}</select></div>}
                {formData.scheduleFrequency === 'custom' && <div className="md:col-span-3"><label className="label">Dias da semana</label><div className="flex flex-wrap gap-2">{weekdays.map((day) => <button key={day.value} type="button" onClick={() => toggleScheduleDay(day.value)} className={cn('px-3 py-1.5 rounded-md text-xs border', formData.scheduleDays.includes(day.value) ? 'bg-brand-500 text-white border-brand-500' : 'border-surface-300 dark:border-surface-600')}>{day.label}</button>)}</div>{formData.scheduleDays.length === 0 && <p className="text-xs text-red-500 mt-1">Selecione ao menos um dia.</p>}</div>}
                <p className="md:col-span-3 text-xs text-surface-500">Horário considerado em America/Sao_Paulo. A primeira execução acontece agora; as próximas seguem o agendamento.</p>
              </div>
            )}
          </div>
          <p className="text-xs text-surface-500">Comece com o perfil rápido. Use “Sem ping” quando a rede bloquear ICMP; ele será mais demorado.</p>
          <div className="flex gap-2">
            <button type="submit" disabled={submitting || executor?.status === 'offline' || (formData.isScheduled && formData.scheduleFrequency === 'custom' && formData.scheduleDays.length === 0)} className="btn-primary">{submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />} Iniciar</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      )}

      <div className="space-y-2">
        {loading ? <div className="card-padded text-center text-surface-400 py-12">Carregando...</div> : scans.length === 0 ? (
          <div className="card-padded text-center text-surface-400 py-12"><Radar className="w-10 h-10 mx-auto mb-3 opacity-40" /><p>Nenhum discovery encontrado</p></div>
        ) : scans.map((scan) => {
          const config = statusConfig[scan.status] || statusConfig.pending
          const StatusIcon = config.icon
          const message = typeof scan.results_summary?.message === 'string' ? scan.results_summary.message : config.label
          const completed = scan.status === 'completed'
          return (
            <button key={scan.id} onClick={() => setSelected(scan)} className="card-padded w-full text-left hover:border-brand-300 dark:hover:border-brand-700 transition-colors">
              <div className="flex items-center gap-4">
                <StatusIcon className={cn('w-5 h-5 shrink-0', config.color)} />
                <div className="flex-1 min-w-0"><div className="flex items-center gap-2"><span className="font-medium text-surface-900 dark:text-white">{scan.name}</span><span className="badge-info text-2xs uppercase">discovery</span>{scan.is_scheduled && <span className="badge-info text-2xs">AGENDADO</span>}</div><p className="text-xs text-surface-500 mt-0.5 truncate">{scan.target} · {message}{scan.is_scheduled && scan.next_run ? ` · próxima: ${formatDate(`${scan.next_run}Z`)}` : ''}</p></div>
                <div className="w-32 hidden md:block"><div className="h-2 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden"><div className={cn('h-full transition-all duration-500', scan.status === 'failed' ? 'bg-red-500' : completed ? 'bg-green-500' : 'bg-brand-500')} style={{ width: `${scan.progress}%` }} /></div><p className="text-2xs text-right text-surface-400 mt-1">{scan.progress}%</p></div>
                <span className="text-xs text-surface-500 min-w-20 text-right">{completed || scan.devices_found > 0 ? `${scan.devices_found} dispositivos` : config.label}</span>
                <span className="text-xs text-surface-400 hidden lg:block">{formatDate(scan.created_at)}</span>
                {(scan.status === 'pending' || scan.status === 'running') && <span onClick={(event) => { event.stopPropagation(); handleCancel(scan.id) }} className="btn-ghost btn-sm text-red-500"><XCircle className="w-4 h-4" /></span>}
              </div>
              {scan.error_message && <p className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/20 rounded px-3 py-1.5">{scan.error_message}</p>}
            </button>
          )
        })}
      </div>

      {selected && <TaskDetailsModal task={selected} onClose={() => setSelected(null)} onCancel={handleCancel} onDisableSchedule={handleDisableSchedule} />}
    </div>
  )
}
