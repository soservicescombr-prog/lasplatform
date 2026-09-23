// netguard/frontend/src/pages/AgentsPage.tsx
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '@/services/api'
import { cn, formatDate } from '@/lib/utils'
import { Shield, Plus, Trash2, Loader2, Copy, Check } from 'lucide-react'
import toast from 'react-hot-toast'

interface Agent {
  id: string; hostname: string; platform: string; platform_version: string;
  agent_version: string; is_active: boolean; last_heartbeat: string | null;
  last_report: string | null; created_at: string;
}

export function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [showRegister, setShowRegister] = useState(false)
  const [hostname, setHostname] = useState('')
  const [registering, setRegistering] = useState(false)
  const [newToken, setNewToken] = useState('')
  const [copied, setCopied] = useState(false)

  const fetchAgents = async () => {
    try {
      const { data } = await api.get('/agents')
      setAgents(data.items)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchAgents() }, [])

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!hostname) return
    setRegistering(true)
    try {
      const { data } = await api.post('/agents/register', { hostname })
      setNewToken(data.agent_token)
      toast.success('Agente registrado')
      fetchAgents()
    } catch { toast.error('Erro ao registrar') }
    finally { setRegistering(false) }
  }

  const handleDeactivate = async (id: string) => {
    if (!confirm('Desativar agente?')) return
    try {
      await api.delete(`/agents/${id}`)
      toast.success('Agente desativado')
      fetchAgents()
    } catch { toast.error('Erro') }
  }

  const copyToken = () => {
    navigator.clipboard.writeText(newToken)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
    toast.success('Token copiado')
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Agentes</h1>
          <p className="text-sm text-surface-500 mt-0.5">Agentes de scan instalados em hosts</p>
        </div>
        <button onClick={() => setShowRegister(!showRegister)} className="btn-primary">
          <Plus className="w-4 h-4" /> Registrar agente
        </button>
      </div>

      {/* Register form */}
      {showRegister && (
        <div className="card-padded space-y-4">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Registrar novo agente</h2>
          <form onSubmit={handleRegister} className="flex gap-3">
            <input className="input flex-1" placeholder="Hostname do servidor/estação" value={hostname}
              onChange={(e) => setHostname(e.target.value)} required />
            <button type="submit" disabled={registering} className="btn-primary">
              {registering ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Registrar'}
            </button>
          </form>

          {/* Token display */}
          {newToken && (
            <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4">
              <p className="text-sm font-semibold text-green-700 dark:text-green-400 mb-2">Token gerado (copie e configure no agente):</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 text-xs bg-white dark:bg-surface-800 p-2 rounded font-mono break-all border">{newToken}</code>
                <button onClick={copyToken} className="btn-secondary btn-sm shrink-0">
                  {copied ? <Check className="w-4 h-4 text-green-500" /> : <Copy className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-green-600 dark:text-green-500 mt-2">
                Insira no arquivo ~/.netguard-agent.json do host como "agent_token"
              </p>
            </div>
          )}
        </div>
      )}

      {/* Agent list */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <th className="text-left px-5 py-3 font-medium text-surface-500">Hostname</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Plataforma</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Versão agente</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Status</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Último heartbeat</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Último relatório</th>
              <th className="text-right px-5 py-3 font-medium text-surface-500">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={7} className="text-center py-8 text-surface-400">Carregando...</td></tr>
            ) : agents.length === 0 ? (
              <tr><td colSpan={7} className="text-center py-8 text-surface-400">
                <Shield className="w-8 h-8 mx-auto mb-2 opacity-40" />
                Nenhum agente registrado
              </td></tr>
            ) : agents.map((a) => (
              <tr key={a.id} className="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/30">
                <td className="px-5 py-3 font-medium text-surface-900 dark:text-white">{a.hostname || '—'}</td>
                <td className="px-5 py-3 text-surface-600 dark:text-surface-400">{a.platform || '—'} {a.platform_version || ''}</td>
                <td className="px-5 py-3 font-mono text-surface-500">{a.agent_version || '—'}</td>
                <td className="px-5 py-3">
                  <span className={cn('badge', a.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'badge-info')}>
                    {a.is_active ? 'Ativo' : 'Inativo'}
                  </span>
                </td>
                <td className="px-5 py-3 text-xs text-surface-500">{a.last_heartbeat ? formatDate(a.last_heartbeat) : '—'}</td>
                <td className="px-5 py-3 text-xs text-surface-500">{a.last_report ? formatDate(a.last_report) : '—'}</td>
                <td className="px-5 py-3 text-right">
                  <Link to={`/agents/${a.id}`} className="btn-secondary btn-sm mr-2">Detalhes</Link>
                  <button onClick={() => handleDeactivate(a.id)} className="btn-ghost btn-sm text-red-500" title="Desativar">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
