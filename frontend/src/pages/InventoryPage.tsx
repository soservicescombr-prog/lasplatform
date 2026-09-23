// netguard/frontend/src/pages/InventoryPage.tsx
import { useEffect, useState } from 'react'
import api from '@/services/api'
import { Package, Edit2, X } from 'lucide-react'
import toast from 'react-hot-toast'

interface InvItem {
  id: string; device_id: string; asset_tag: string; serial_number: string;
  device_ip?: string; device_name?: string; device_vendor?: string;
  department: string; responsible: string; location_building: string;
  location_room: string; location_rack: string; criticality: string;
  environment: string; business_service: string; support_contract: string;
  custom_fields: Record<string, string>; notes: string;
}

const critColors: Record<string, string> = {
  critical: 'badge-critical', high: 'badge-high', medium: 'badge-medium', low: 'badge-low',
}

export function InventoryPage() {
  const [items, setItems] = useState<InvItem[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)
  const [search] = useState('')
  const [editId, setEditId] = useState<string | null>(null)
  const [editForm, setEditForm] = useState<Partial<InvItem>>({})

  const fetchItems = async () => {
    setLoading(true)
    try {
      const params: Record<string, unknown> = { page, page_size: 20 }
      if (search) params.search = search
      const { data } = await api.get('/extras/inventory', { params })
      setItems(data.items)
      setTotal(data.total)
    } catch { /* */ }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchItems() }, [page])

  const handleSave = async (id: string) => {
    try {
      await api.put(`/extras/inventory/${id}`, editForm)
      toast.success('Item atualizado')
      setEditId(null)
      fetchItems()
    } catch { toast.error('Erro ao salvar') }
  }

  const totalPages = Math.ceil(total / 20)

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-surface-900 dark:text-white">Inventário / CMDB</h1>
          <p className="text-sm text-surface-500 mt-0.5">{total} itens registrados</p>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-surface-200 dark:border-surface-700 bg-surface-50 dark:bg-surface-800/50">
                {['Dispositivo', 'Asset Tag', 'Departamento', 'Responsável', 'Local', 'Criticidade', 'Ambiente', 'Serviço', 'Contrato', 'Ações'].map(h => (
                  <th key={h} className="text-left px-4 py-3 font-medium text-surface-500 text-xs whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={10} className="text-center py-8 text-surface-400">Carregando...</td></tr>
              ) : items.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-8 text-surface-400">
                  <Package className="w-8 h-8 mx-auto mb-2 opacity-40" />
                  Nenhum item no inventário. Cadastre via API ou vincule a dispositivos.
                </td></tr>
              ) : items.map(item => (
                <tr key={item.id} className="border-b border-surface-100 dark:border-surface-800 hover:bg-surface-50 dark:hover:bg-surface-800/30">
                  <td className="px-4 py-2"><p className="font-mono text-xs text-surface-900 dark:text-white">{item.device_ip || '—'}</p><p className="text-2xs text-surface-500">{item.device_name || item.device_vendor || 'Dispositivo descoberto'}</p></td>
                  <td className="px-4 py-2 font-mono font-medium text-surface-900 dark:text-white">{item.asset_tag || '—'}</td>
                  <td className="px-4 py-2 text-surface-600 dark:text-surface-400">
                    {editId === item.id ? (
                      <input className="input py-0.5 text-xs w-28" value={editForm.department || ''}
                        onChange={e => setEditForm(f => ({ ...f, department: e.target.value }))} />
                    ) : item.department || '—'}
                  </td>
                  <td className="px-4 py-2 text-surface-600 dark:text-surface-400">
                    {editId === item.id ? (
                      <input className="input py-0.5 text-xs w-28" value={editForm.responsible || ''}
                        onChange={e => setEditForm(f => ({ ...f, responsible: e.target.value }))} />
                    ) : item.responsible || '—'}
                  </td>
                  <td className="px-4 py-2 text-xs text-surface-500">{[item.location_building, item.location_room, item.location_rack].filter(Boolean).join(' / ') || '—'}</td>
                  <td className="px-4 py-2"><span className={critColors[item.criticality] || 'badge-info'}>{item.criticality}</span></td>
                  <td className="px-4 py-2 text-surface-500">{item.environment || '—'}</td>
                  <td className="px-4 py-2 text-surface-500">{item.business_service || '—'}</td>
                  <td className="px-4 py-2 text-surface-500">{item.support_contract || '—'}</td>
                  <td className="px-4 py-2">
                    {editId === item.id ? (
                      <div className="flex gap-1">
                        <button onClick={() => handleSave(item.id)} className="btn-primary btn-sm text-xs">Salvar</button>
                        <button onClick={() => setEditId(null)} className="btn-ghost btn-sm"><X className="w-3.5 h-3.5" /></button>
                      </div>
                    ) : (
                      <button onClick={() => { setEditId(item.id); setEditForm(item) }} className="btn-ghost btn-sm"><Edit2 className="w-3.5 h-3.5" /></button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
