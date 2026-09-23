// netguard/frontend/src/pages/SNMPPage.tsx
import { useEffect, useState } from 'react'
import api from '@/services/api'
import type { SNMPCommunity, SNMPInterface } from '@/types'
import { cn, formatBps } from '@/lib/utils'
import { Plus, Trash2, ArrowUpDown, X } from 'lucide-react'
import toast from 'react-hot-toast'

export function SNMPPage() {
  const [communities, setCommunities] = useState<SNMPCommunity[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', community_string: '', snmp_version: 'v2c', description: '' })
  // Interface viewer
  const [interfaces, setInterfaces] = useState<SNMPInterface[]>([])

  const fetchCommunities = async () => {
    try {
      const { data } = await api.get('/snmp/communities')
      setCommunities(data)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchCommunities() }, [])

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await api.post('/snmp/communities', form)
      toast.success('Community criada')
      setShowForm(false)
      setForm({ name: '', community_string: '', snmp_version: 'v2c', description: '' })
      fetchCommunities()
    } catch { toast.error('Erro ao criar') }
  }

  const handleDelete = async (id: string) => {
    if (!confirm('Remover community?')) return
    try {
      await api.delete(`/snmp/communities/${id}`)
      toast.success('Removida')
      fetchCommunities()
    } catch { toast.error('Erro') }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">SNMP</h1>
          <p className="text-sm text-surface-500 mt-0.5">Gerenciar communities e coletas SNMP</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus className="w-4 h-4" /> Nova Community
        </button>
      </div>

      {/* Create form */}
      {showForm && (
        <form onSubmit={handleCreate} className="card-padded space-y-4">
          <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300">Nova SNMP Community</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="label">Nome</label>
              <input className="input" placeholder="Ex: Switches Core" value={form.name}
                onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} required />
            </div>
            <div>
              <label className="label">Community String</label>
              <input className="input font-mono" placeholder="public" value={form.community_string}
                onChange={(e) => setForm(f => ({ ...f, community_string: e.target.value }))} required />
            </div>
            <div>
              <label className="label">Versão SNMP</label>
              <select className="input" value={form.snmp_version}
                onChange={(e) => setForm(f => ({ ...f, snmp_version: e.target.value }))}>
                <option value="v1">v1</option>
                <option value="v2c">v2c</option>
                <option value="v3">v3</option>
              </select>
            </div>
            <div>
              <label className="label">Descrição</label>
              <input className="input" placeholder="Descrição opcional" value={form.description}
                onChange={(e) => setForm(f => ({ ...f, description: e.target.value }))} />
            </div>
          </div>
          <div className="flex gap-2">
            <button type="submit" className="btn-primary"><Plus className="w-4 h-4" /> Criar</button>
            <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancelar</button>
          </div>
        </form>
      )}

      {/* Communities list */}
      <div className="card overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
              <th className="text-left px-5 py-3 font-medium text-surface-500">Nome</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Community</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Versão</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Descrição</th>
              <th className="text-left px-5 py-3 font-medium text-surface-500">Status</th>
              <th className="text-right px-5 py-3 font-medium text-surface-500">Ações</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan={6} className="text-center py-8 text-surface-400">Carregando...</td></tr>
            ) : communities.length === 0 ? (
              <tr><td colSpan={6} className="text-center py-8 text-surface-400">Nenhuma community cadastrada</td></tr>
            ) : communities.map((c) => (
              <tr key={c.id} className="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/30">
                <td className="px-5 py-3 font-medium text-surface-900 dark:text-white">{c.name}</td>
                <td className="px-5 py-3 font-mono text-surface-600 dark:text-surface-400">{c.community_string}</td>
                <td className="px-5 py-3"><span className="badge-info">{c.snmp_version}</span></td>
                <td className="px-5 py-3 text-surface-500">{c.description || '—'}</td>
                <td className="px-5 py-3">
                  <span className={cn('badge', c.is_active ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' : 'badge-info')}>
                    {c.is_active ? 'Ativa' : 'Inativa'}
                  </span>
                </td>
                <td className="px-5 py-3 text-right">
                  <button onClick={() => handleDelete(c.id)} className="btn-ghost btn-sm text-red-500"><Trash2 className="w-3.5 h-3.5" /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Interface viewer (if device selected via query param or modal) */}
      {interfaces.length > 0 && (
        <div className="card overflow-hidden">
          <div className="px-5 py-3 border-b border-surface-200 dark:border-surface-700 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-surface-700 dark:text-surface-300 flex items-center gap-2">
              <ArrowUpDown className="w-4 h-4" /> Interfaces do dispositivo
            </h2>
            <button onClick={() => setInterfaces([])} className="btn-ghost btn-sm"><X className="w-4 h-4" /></button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="bg-surface-50 dark:bg-surface-800/50 border-b border-surface-200 dark:border-surface-700">
                  <th className="text-left px-4 py-2 font-medium text-surface-500">Interface</th>
                  <th className="text-left px-4 py-2 font-medium text-surface-500">Status</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Speed</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">In (bps)</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Out (bps)</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Util In</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Util Out</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Errors In</th>
                  <th className="text-right px-4 py-2 font-medium text-surface-500">Errors Out</th>
                </tr>
              </thead>
              <tbody>
                {interfaces.map((iface) => (
                  <tr key={iface.id} className="border-b border-surface-100 dark:border-surface-800">
                    <td className="px-4 py-2">
                      <span className="font-mono font-medium text-surface-900 dark:text-white">{iface.if_name || iface.if_descr || `if${iface.if_index}`}</span>
                      {iface.if_alias && <span className="text-surface-400 ml-1">({iface.if_alias})</span>}
                    </td>
                    <td className="px-4 py-2">
                      <span className={cn('status-dot mr-1', iface.if_oper_status === 1 ? 'status-online' : 'status-offline')} />
                      {iface.if_oper_status === 1 ? 'Up' : 'Down'}
                    </td>
                    <td className="px-4 py-2 text-right font-mono">{iface.if_high_speed ? `${iface.if_high_speed} Mbps` : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-green-600 dark:text-green-400">{iface.in_bps != null ? formatBps(iface.in_bps) : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-brand-600 dark:text-brand-400">{iface.out_bps != null ? formatBps(iface.out_bps) : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono">{iface.utilization_in != null ? `${iface.utilization_in.toFixed(1)}%` : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono">{iface.utilization_out != null ? `${iface.utilization_out.toFixed(1)}%` : '—'}</td>
                    <td className="px-4 py-2 text-right font-mono text-red-500">{iface.if_in_errors || 0}</td>
                    <td className="px-4 py-2 text-right font-mono text-red-500">{iface.if_out_errors || 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
