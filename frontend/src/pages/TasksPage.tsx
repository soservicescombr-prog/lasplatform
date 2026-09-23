import { useEffect, useState } from 'react'
import { scansApi } from '@/services/api'
import type { ScanJob } from '@/types'
import { TaskDetailsModal } from '@/components/scans/TaskDetailsModal'
import { cn, formatDate } from '@/lib/utils'
import { AlertCircle, CheckCircle2, Clock, ListTodo, Loader2, XCircle } from 'lucide-react'
import toast from 'react-hot-toast'

const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-yellow-500', label: 'Pendente' },
  running: { icon: Loader2, color: 'text-brand-500 animate-spin', label: 'Executando' },
  completed: { icon: CheckCircle2, color: 'text-green-500', label: 'Concluída' },
  failed: { icon: AlertCircle, color: 'text-red-500', label: 'Falhou' },
  cancelled: { icon: XCircle, color: 'text-surface-400', label: 'Cancelada' },
}

export function TasksPage() {
  const [tasks, setTasks] = useState<ScanJob[]>([])
  const [selected, setSelected] = useState<ScanJob | null>(null)
  const [status, setStatus] = useState('')
  const [loading, setLoading] = useState(true)

  const fetchTasks = async () => {
    try {
      const params: Record<string, unknown> = { page_size: 100 }
      if (status) params.status = status
      const { data } = await scansApi.list(params)
      setTasks(data.items)
      setSelected((current) => current ? data.items.find((item: ScanJob) => item.id === current.id) || current : null)
    } catch { toast.error('Não foi possível atualizar as tasks') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    fetchTasks()
    const interval = setInterval(fetchTasks, 3000)
    return () => clearInterval(interval)
  }, [status])

  const cancelTask = async (id: string) => {
    try { await scansApi.cancel(id); toast.success('Cancelamento solicitado'); fetchTasks() }
    catch { toast.error('Não foi possível cancelar a task') }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Tasks</h1>
          <p className="text-sm text-surface-500 mt-0.5">Histórico e detalhes das execuções assíncronas</p>
        </div>
        <select className="input w-44" value={status} onChange={(event) => setStatus(event.target.value)}>
          <option value="">Todos os status</option>
          <option value="pending">Pendentes</option>
          <option value="running">Executando</option>
          <option value="completed">Concluídas</option>
          <option value="failed">Com falha</option>
          <option value="cancelled">Canceladas</option>
        </select>
      </div>

      {loading ? <div className="card-padded text-center">Carregando...</div> : tasks.length === 0 ? (
        <div className="card-padded text-center text-surface-400 py-12"><ListTodo className="w-10 h-10 mx-auto mb-3 opacity-40" />Nenhuma task encontrada</div>
      ) : (
        <div className="space-y-2">
          {tasks.map((task) => {
            const config = statusConfig[task.status] || statusConfig.pending
            const Icon = config.icon
            const message = typeof task.results_summary?.message === 'string' ? task.results_summary.message : config.label
            return (
              <button key={task.id} onClick={() => setSelected(task)} className="card-padded w-full text-left hover:border-brand-300 dark:hover:border-brand-700 transition-colors">
                <div className="flex items-center gap-4">
                  <Icon className={cn('w-5 h-5 shrink-0', config.color)} />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2"><span className="font-medium">{task.name}</span><span className="badge-info text-2xs">{task.scan_type}</span></div>
                    <p className="text-xs text-surface-500 truncate">{message}</p>
                  </div>
                  <div className="w-32 hidden md:block">
                    <div className="h-1.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden"><div className="h-full bg-brand-500" style={{ width: `${task.progress}%` }} /></div>
                    <p className="text-2xs text-right text-surface-400 mt-1">{task.progress}%</p>
                  </div>
                  <span className="text-xs text-surface-400 hidden sm:block">{formatDate(task.created_at)}</span>
                </div>
              </button>
            )
          })}
        </div>
      )}

      {selected && <TaskDetailsModal task={selected} onClose={() => setSelected(null)} onCancel={cancelTask} />}
    </div>
  )
}
