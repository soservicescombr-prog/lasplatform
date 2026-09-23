import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, Copy, KeyRound, RefreshCw, Save } from 'lucide-react'
import toast from 'react-hot-toast'
import api from '@/services/api'
import { MetricLineChart } from '@/components/metrics/MetricLineChart'
import { formatDate } from '@/lib/utils'

export function AgentDetailsPage() {
  const { id = '' } = useParams(); const navigate = useNavigate()
  const [data, setData] = useState<any>(null); const [paths, setPaths] = useState(''); const [minutes, setMinutes] = useState(60); const [newToken, setNewToken] = useState('')
  const load = async () => { try {
    const response = (await api.get(`/agents/${id}/details`, { params: { minutes } })).data || {}
    const result = {
      ...response,
      agent: response.agent || {},
      metrics: Array.isArray(response.metrics) ? response.metrics : [],
      baselines: Array.isArray(response.baselines) ? response.baselines : [],
      logs: Array.isArray(response.logs) ? response.logs : [],
      alerts: Array.isArray(response.alerts) ? response.alerts : [],
    }
    setData(result)
    setPaths((Array.isArray(result.agent.config?.log_paths) ? result.agent.config.log_paths : []).join('\n'))
  } catch { toast.error('Falha ao carregar o agente') } }
  useEffect(() => { load() }, [id, minutes])
  const save = async () => { try { await api.put(`/agents/${id}/config`, { log_paths: paths.split('\n').map(x => x.trim()).filter(Boolean), metrics_interval_seconds: 15, heartbeat_interval_seconds: 15, log_batch_size: 500 }); toast.success('Configuração enviada ao agente'); load() } catch { toast.error('Falha ao salvar') } }
  const rotateToken = async () => { if (!window.confirm('Rotacionar o token? O token atual deixará de funcionar imediatamente.')) return; try { const response = await api.post(`/agents/${id}/rotate-token`); setNewToken(response.data.agent_token); toast.success('Novo token gerado') } catch { toast.error('Falha ao rotacionar o token') } }
  if (!data) return <div className="card-padded">Carregando...</div>
  const a = data.agent || {}; const metrics = data.metrics || []; const baselines = data.baselines || []; const logs = data.logs || []; const alerts = data.alerts || []; const latest = metrics.at(-1) || {}
  return <div className="space-y-5">
    <div className="flex items-center justify-between"><div className="flex items-center gap-3"><button className="btn-ghost" onClick={() => navigate(-1)}><ArrowLeft className="w-4 h-4" /></button><div><h1 className="text-xl font-bold">{a.hostname || a.id}</h1><p className="text-sm text-surface-500">{a.platform || '—'} · {a.is_online ? 'online' : 'offline'} · heartbeat {a.last_heartbeat ? formatDate(a.last_heartbeat) : 'nunca'}</p></div></div><div className="flex gap-2"><button className="btn-secondary" onClick={rotateToken}><KeyRound className="w-4 h-4" /> Novo token</button><select className="input w-auto" value={minutes} onChange={e => setMinutes(Number(e.target.value))}><option value={5}>5 minutos</option><option value={15}>15 minutos</option><option value={60}>1 hora</option><option value={360}>6 horas</option><option value={1440}>24 horas</option><option value={10080}>7 dias</option><option value={43200}>30 dias</option></select><button className="btn-secondary" onClick={load}><RefreshCw className="w-4 h-4" /></button></div></div>
    {newToken && <div className="card-padded border border-amber-400"><p className="font-semibold">Novo token — copie agora; ele não será exibido novamente.</p><div className="flex gap-2 mt-2"><input className="input font-mono text-xs" readOnly value={newToken} /><button className="btn-secondary" onClick={() => { navigator.clipboard.writeText(newToken); toast.success('Token copiado') }}><Copy className="w-4 h-4" /> Copiar</button></div><p className="text-xs text-surface-500 mt-2">Substitua <code>agent_token</code> em ~/.netguard-agent.json e reinicie o agente.</p></div>}
    <div className="grid grid-cols-3 gap-3">{[['CPU', latest.cpu_usage], ['Memória', latest.memory_usage], ['Disco', latest.disk_usage]].map(([label, value]) => <div className="card-padded" key={String(label)}><p className="text-2xl font-bold">{value == null ? '—' : `${Number(value).toFixed(1)}%`}</p><p className="text-xs text-surface-500">{label}</p></div>)}</div>
    <div className="grid lg:grid-cols-2 gap-4"><div className="card-padded"><h2 className="font-semibold mb-3">Recursos</h2><MetricLineChart data={metrics} unit="%" lines={[{ key: 'cpu_usage', name: 'CPU', color: '#6366f1' }, { key: 'memory_usage', name: 'Memória', color: '#10b981' }, { key: 'disk_usage', name: 'Disco', color: '#f59e0b' }]} /></div><div className="card-padded"><h2 className="font-semibold mb-3">Carga</h2><MetricLineChart data={metrics} lines={[{ key: 'load_1m', name: '1 min', color: '#8b5cf6' }, { key: 'load_5m', name: '5 min', color: '#ec4899' }, { key: 'load_15m', name: '15 min', color: '#0ea5e9' }]} /></div></div>
    <div className="grid lg:grid-cols-2 gap-4"><div className="card-padded"><h2 className="font-semibold mb-3">Baselines</h2><div className="space-y-2">{baselines.map((b:any) => <div key={b.metric_name} className="border rounded p-3 text-sm flex justify-between"><span>{b.metric_name} · {b.status} ({b.samples} amostras)</span><span>média {Number(b.mean).toFixed(2)} · limite {b.upper_bound == null ? '—' : Number(b.upper_bound).toFixed(2)}</span></div>)}{!baselines.length && <p className="text-sm text-surface-400">Baseline ainda não disponível. A coleta começa após o primeiro heartbeat do agente atualizado.</p>}</div></div><div className="card-padded"><h2 className="font-semibold mb-2">Arquivos de log monitorados</h2><textarea className="input min-h-32 font-mono text-xs" value={paths} onChange={e => setPaths(e.target.value)} placeholder={'/var/log/syslog\n/var/log/nginx/*.log'} /><button className="btn-primary mt-2" onClick={save}><Save className="w-4 h-4" /> Salvar</button></div></div>
    <div className="card overflow-hidden"><div className="p-4 border-b font-semibold">Logs recentes</div><div className="max-h-80 overflow-auto">{logs.map((log:any) => <div key={log.id} className="p-3 border-b text-xs"><span className="font-mono text-surface-400">{formatDate(log.timestamp)} · {log.path || 'agent'}</span><p className="font-mono mt-1 break-all">{log.message}</p></div>)}{!logs.length && <p className="p-5 text-surface-400">Nenhum log recebido.</p>}</div></div>
    <div className="card-padded"><h2 className="font-semibold mb-3">Alertas</h2>{alerts.map((x:any) => <div className="border rounded p-3 mb-2" key={x.id}><b>{x.title}</b><p className="text-sm text-surface-500">{x.message}</p></div>)}{!alerts.length && <p className="text-sm text-surface-400">Nenhum alerta.</p>}</div>
  </div>
}
