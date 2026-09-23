import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import api from '@/services/api'
import { MetricLineChart } from '@/components/metrics/MetricLineChart'
import { formatBps, formatDate } from '@/lib/utils'
import toast from 'react-hot-toast'

export function DeviceDetailsPage() {
  const { id = '' } = useParams(); const navigate = useNavigate(); const [data, setData] = useState<any>(null)
  const load = async () => { try {
    const response = (await api.get(`/devices/${id}/details`)).data || {}
    setData({ ...response, device: response.device || {},
      metrics: Array.isArray(response.metrics) ? response.metrics : [],
      interfaces: Array.isArray(response.interfaces) ? response.interfaces : [],
      logs: Array.isArray(response.logs) ? response.logs : [],
      alerts: Array.isArray(response.alerts) ? response.alerts : [] })
  } catch { toast.error('Falha ao carregar o dispositivo') } }
  useEffect(() => { load() }, [id]); if (!data) return <div className="card-padded">Carregando...</div>
  const d = data.device || {}; const metrics = data.metrics || []; const interfaces = data.interfaces || []; const logs = data.logs || []; const alerts = data.alerts || []
  return <div className="space-y-5"><div className="flex justify-between"><div className="flex items-center gap-3"><button className="btn-ghost" onClick={() => navigate(-1)}><ArrowLeft className="w-4 h-4" /></button><div><h1 className="text-xl font-bold">{d.hostname || d.snmp_sys_name || d.ip_address}</h1><p className="font-mono text-sm text-surface-500">{d.ip_address} · {d.vendor || 'fabricante desconhecido'} {d.model || ''}</p></div></div><button className="btn-secondary" onClick={load}><RefreshCw className="w-4 h-4" /> Atualizar</button></div>
    <div className="grid lg:grid-cols-2 gap-4"><div className="card-padded"><h2 className="font-semibold mb-3">CPU, memória e disco</h2><MetricLineChart data={metrics} unit="%" lines={[{ key: 'cpu_usage', name: 'CPU', color: '#6366f1' }, { key: 'memory_usage', name: 'Memória', color: '#10b981' }, { key: 'disk_usage', name: 'Disco', color: '#f59e0b' }]} /></div><div className="card-padded"><h2 className="font-semibold mb-3">Tráfego agregado (bps)</h2><MetricLineChart data={metrics} lines={[{ key: 'in_bps', name: 'Entrada', color: '#10b981' }, { key: 'out_bps', name: 'Saída', color: '#3b82f6' }]} /></div></div>
    <div className="card overflow-x-auto"><div className="p-4 font-semibold">Interfaces ({interfaces.length})</div><table className="w-full text-xs"><thead><tr><th className="p-3 text-left">Interface</th><th>Status</th><th>Entrada</th><th>Saída</th><th>Erros</th></tr></thead><tbody>{interfaces.map((x:any) => <tr className="border-t" key={x.id}><td className="p-3 font-mono">{x.name}{x.alias ? ` · ${x.alias}` : ''}</td><td className="text-center">{x.oper_status === 1 ? 'Up' : 'Down'}</td><td className="text-center">{formatBps(x.in_bps || 0)}</td><td className="text-center">{formatBps(x.out_bps || 0)}</td><td className="text-center">{(x.in_errors || 0) + (x.out_errors || 0)}</td></tr>)}</tbody></table>{!interfaces.length && <p className="p-5 text-center text-surface-400">Nenhuma interface coletada.</p>}</div>
    <div className="grid lg:grid-cols-2 gap-4"><div className="card-padded"><h2 className="font-semibold mb-3">Logs recentes</h2>{logs.map((x:any) => <div className="border-b py-2 text-xs" key={x.id}><span className="text-surface-400">{formatDate(x.timestamp)} · {x.severity}</span><p className="font-mono break-all">{x.message}</p></div>)}{!logs.length && <p className="text-sm text-surface-400">Nenhum log correlacionado.</p>}</div><div className="card-padded"><h2 className="font-semibold mb-3">Alertas</h2>{alerts.map((x:any) => <div className="border rounded p-3 mb-2" key={x.id}><b>{x.title}</b><p className="text-sm text-surface-500">{x.message}</p></div>)}{!alerts.length && <p className="text-sm text-surface-400">Nenhum alerta.</p>}</div></div>
  </div>
}
