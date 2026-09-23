import type { ScanJob } from '@/types'
import { cn, formatDate } from '@/lib/utils'
import { AlertCircle, CheckCircle2, Clock, Loader2, X, XCircle } from 'lucide-react'

const statusConfig: Record<string, { icon: React.ElementType; color: string; label: string }> = {
  pending: { icon: Clock, color: 'text-yellow-500', label: 'Pendente' },
  running: { icon: Loader2, color: 'text-brand-500 animate-spin', label: 'Executando' },
  completed: { icon: CheckCircle2, color: 'text-green-500', label: 'Concluída' },
  failed: { icon: AlertCircle, color: 'text-red-500', label: 'Falhou' },
  cancelled: { icon: XCircle, color: 'text-surface-400', label: 'Cancelada' },
}

export function TaskDetailsModal({
  task,
  onClose,
  onCancel,
  onDisableSchedule,
}: {
  task: ScanJob
  onClose: () => void
  onCancel?: (id: string) => void
  onDisableSchedule?: (id: string) => void
}) {
  const config = statusConfig[task.status] || statusConfig.pending
  const StatusIcon = config.icon
  const summary = task.results_summary || {}
  const stage = typeof summary.stage === 'string' ? summary.stage : 'queued'
  const message = typeof summary.message === 'string' ? summary.message : 'Aguardando informações do executor'

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="card w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-200 dark:border-surface-700">
          <div className="flex items-center gap-3">
            <StatusIcon className={cn('w-5 h-5', config.color)} />
            <div>
              <h2 className="font-semibold text-surface-900 dark:text-white">{task.name}</h2>
              <p className="text-xs text-surface-500">{config.label} · {stage}</p>
            </div>
          </div>
          <button onClick={onClose} className="btn-ghost btn-sm"><X className="w-4 h-4" /></button>
        </div>

        <div className="p-5 space-y-5">
          <div>
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-surface-600 dark:text-surface-300">{message}</span>
              <span className="font-mono text-surface-500">{task.progress}%</span>
            </div>
            <div className="h-2.5 bg-surface-200 dark:bg-surface-700 rounded-full overflow-hidden">
              <div className={cn('h-full transition-all duration-500', task.status === 'failed' ? 'bg-red-500' : task.status === 'completed' ? 'bg-green-500' : 'bg-brand-500')}
                style={{ width: `${task.progress}%` }} />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
            <div><span className="label">Tipo</span><p>{task.scan_type}</p></div>
            <div><span className="label">Alvo</span><p className="font-mono">{task.target}</p></div>
            <div><span className="label">Criada</span><p>{formatDate(task.created_at)}</p></div>
            <div><span className="label">Iniciada</span><p>{task.started_at ? formatDate(task.started_at) : '—'}</p></div>
            <div><span className="label">Finalizada</span><p>{task.completed_at ? formatDate(task.completed_at) : '—'}</p></div>
            <div><span className="label">ID da task</span><p className="font-mono text-xs break-all">{task.celery_task_id || '—'}</p></div>
            <div><span className="label">Dispositivos</span><p>{task.devices_found}</p></div>
            <div><span className="label">Vulnerabilidades</span><p>{task.vulnerabilities_found}</p></div>
            <div><span className="label">Agendamento</span><p>{task.is_scheduled ? 'Ativo' : 'Não agendado'}</p></div>
            <div><span className="label">Próxima execução</span><p>{task.next_run ? formatDate(`${task.next_run}Z`) : '—'}</p></div>
          </div>

          {task.error_message && (
            <div className="rounded-lg bg-red-50 dark:bg-red-950/30 border border-red-200 dark:border-red-900 p-3">
              <p className="text-xs font-semibold text-red-700 dark:text-red-400 mb-1">Erro da execução</p>
              <pre className="text-xs text-red-600 dark:text-red-300 whitespace-pre-wrap break-words">{task.error_message}</pre>
            </div>
          )}

          <div>
            <p className="label mb-1">Resultado e dados da execução</p>
            <pre className="text-xs bg-surface-50 dark:bg-surface-950 rounded-lg p-3 overflow-auto whitespace-pre-wrap">
              {JSON.stringify(summary, null, 2)}
            </pre>
          </div>

          {(task.status === 'pending' || task.status === 'running') && onCancel && (
            <div className="flex justify-end">
              <button onClick={() => onCancel(task.id)} className="btn-secondary text-red-500">
                <XCircle className="w-4 h-4" /> Cancelar execução
              </button>
            </div>
          )}
          {task.is_scheduled && onDisableSchedule && (
            <div className="flex justify-end">
              <button onClick={() => onDisableSchedule(task.id)} className="btn-secondary text-red-500">
                <XCircle className="w-4 h-4" /> Desativar agendamento
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
